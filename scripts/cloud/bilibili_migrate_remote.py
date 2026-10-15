"""Reviewed operator program: stdin-only SESSDATA, one nav check, atomic grant.

Executed through a trusted release Python, without a website session or server
restart. No public collection, source retry changes or local credential files.
"""
import asyncio
import json
import logging
import sqlite3
import sys
from uuid import uuid4

PROVIDER='bilibili-public-source'
MAX_INPUT=32768
SAFE_CODES=frozenset({'invalid_input','configuration_unavailable','unique_admin_required',
    'authorization_changed','storage_unavailable','upstream_unavailable',
    'invalid_credentials','upstream_restricted','rate_limited','upstream_rejected',
    'unsupported_response','verification_timeout','operation_failed'})


class MigrationError(ValueError):
    pass


def unique_admin(connection):
    rows=connection.execute('SELECT user_id FROM users WHERE is_admin=1 AND disabled_at IS NULL ORDER BY user_id').fetchall()
    if len(rows)!=1:raise MigrationError('unique_admin_required')
    return rows[0][0]


def current_grants(connection):
    return connection.execute("SELECT grant_id,user_id,version FROM grants WHERE provider=? AND state='active' ORDER BY grant_id",(PROVIDER,)).fetchall()


async def authorize(connection, credentials, sessdata, *, provider=None):
    from game_assistant.accounts.service import transaction
    from game_assistant.auth.bilibili_provider import BilibiliLoginProvider, VerifiedBilibiliAccount, normalize_cookie_input, LIMITS
    if not isinstance(sessdata,str) or not sessdata or len(sessdata)>4096:
        raise MigrationError('invalid_input')
    # Capture a consistent pre-validation baseline. No database lock is held
    # across the one upstream nav request.
    with transaction(connection):
        owner,previous=unique_admin(connection),current_grants(connection)
    provider=provider if provider is not None else BilibiliLoginProvider()
    try:
        async with asyncio.timeout(20):
            verified=await provider.validate_credentials(normalize_cookie_input({'sessdata':sessdata}))
    finally:
        await provider.aclose()
    if not isinstance(verified,VerifiedBilibiliAccount):raise MigrationError('invalid_credentials')
    values={'bilibili':{key:value for key,value in verified.credentials.items() if key in LIMITS},
        'bilibili_meta':{'uid':verified.uid,'nickname':verified.nickname,'validated_at':verified.validated_at}}
    with transaction(connection):
        if unique_admin(connection)!=owner or current_grants(connection)!=previous:
            raise MigrationError('authorization_changed')
        grant=str(uuid4())
        sealed=credentials.seal_grant(owner,grant,values,1)
        connection.execute("UPDATE grants SET state='revoked',version=version+1 WHERE provider=? AND state='active'",(PROVIDER,))
        connection.execute("INSERT INTO grants(grant_id,user_id,provider,state,encrypted_payload) VALUES(?,?,?,'active',?)",(grant,owner,PROVIDER,sealed))
    return {'status':'saved','configured':True}


async def run(config_path, sessdata):
    from contextlib import closing
    from pathlib import Path
    from game_assistant.cloud_runtime import load_runtime
    from game_assistant.auth.store import CredentialStore
    from game_assistant.migrations.offline import identity_schema_valid
    try:runtime=load_runtime(config_path)
    except Exception:raise MigrationError('configuration_unavailable') from None
    # mode=rw never provisions a replacement identity database.
    with closing(sqlite3.connect(Path(runtime.settings.cloud_db_path).as_uri()+'?mode=rw',uri=True,timeout=10)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        version=db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (2,3,4) or not identity_schema_valid(db,version):
            raise MigrationError('configuration_unavailable')
        store=CredentialStore('unused',connection=db,key_path=runtime.settings.cloud_credentials_key_path)
        store._grant_key()  # external owner-only key; never creates or replaces it
        return await authorize(db,store,sessdata)


def main(argv=None):
    logging.disable(logging.CRITICAL)
    sys.dont_write_bytecode=True
    # The operator transports plaintext only in memory; do not emit core dumps.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    except ImportError:pass
    args=sys.argv[1:] if argv is None else argv
    try:
        if len(args)!=1:raise MigrationError('configuration_unavailable')
        raw=sys.stdin.buffer.read(MAX_INPUT+1)
        if len(raw)>MAX_INPUT:raise MigrationError('invalid_input')
        value=json.loads(raw)
        if not isinstance(value,dict) or set(value)!= {'sessdata'}:raise MigrationError('invalid_input')
        result=asyncio.run(run(args[0],value['sessdata']))
        value.clear();raw=b''
        print(json.dumps(result,separators=(',',':')))
        return 0
    except BaseException as error:
        from game_assistant.auth.bilibili_provider import BilibiliProtocolError
        code=(error.error_code.lower() if isinstance(error,BilibiliProtocolError)
              else str(error) if isinstance(error,MigrationError) else
              'verification_timeout' if isinstance(error,TimeoutError) else 'operation_failed')
        if code not in SAFE_CODES:code='operation_failed'
        print(json.dumps({'status':'failed','error_code':code},separators=(',',':')))
        return 1


if __name__=='__main__':raise SystemExit(main())

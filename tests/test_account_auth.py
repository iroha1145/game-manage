import asyncio
import sqlite3

import pytest

from game_assistant.accounts.service import AccountService
from game_assistant.auth.service import LoginError, ScopedLoginService
from game_assistant.auth.store import CredentialStore, CredentialStoreError
from game_assistant.identity.models import Principal
from game_assistant.migrations.cloud_v1 import migrate_cloud_schema


class Provider:
    async def start_context(self):
        return {'device_id': 'device'}

    async def send_sms(self, context, mobile, captcha=None):
        pass

    async def login(self, context, mobile, code):
        return {'center_uid': mobile, 'role_id': '77', 'device_id': 'device',
                'access_token': 'token-' + mobile, 'refresh_token': 'refresh-' + mobile}

    async def renew(self, credentials):
        return {**credentials, 'access_token': 'renewed'}


def setup(tmp_path, provider=None, clock=None):
    db = sqlite3.connect(':memory:')
    migrate_cloud_schema(db)
    db.executemany('INSERT INTO users(user_id,username,password_hash) VALUES(?,?,?)',
                   [('a', 'alice', 'hash'), ('b', 'bob', 'hash')])
    db.commit()
    key = tmp_path / 'cloud.key'
    key.write_bytes(b'x' * 32)
    key.chmod(0o600)
    store = CredentialStore(tmp_path / 'unused', connection=db, key_path=key)
    accounts = AccountService(db, store)
    kwargs = {'clock':clock} if clock is not None else {}
    login = ScopedLoginService(accounts, providers={'tajiduo': provider or Provider()}, **kwargs)
    return db, store, accounts, login


async def authorize(login, user='a', mobile='13800000000'):
    p = Principal(user, False)
    session = await login.start(p, 'tajiduo')
    sid = session['session_id']
    await login.sms(p, 'tajiduo', sid, mobile)
    return await login.login(p, 'tajiduo', sid, mobile, '123456')


async def test_login_session_is_owned(tmp_path):
    db, store, accounts, login = setup(tmp_path)
    sid = (await login.start(Principal('a', False), 'tajiduo'))['session_id']
    with pytest.raises(LoginError) as error:
        await login.sms(Principal('b', False), 'tajiduo', sid, '13800000000')
    assert error.value.status == 404
    await login.sms(Principal('a', False), 'tajiduo', sid, '13800000000')
    with pytest.raises(LoginError):
        await login.login(Principal('b', False), 'tajiduo', sid, '13800000000', '123456')
    assert accounts.list_accounts(Principal('b', False)) == []


async def test_verified_login_creates_owned_account_without_exposing_credentials(tmp_path):
    db, store, accounts, login = setup(tmp_path)
    result = await authorize(login)
    assert 'token-' not in str(result)
    assert '13800000000' not in str(result)
    row = accounts.list_accounts(Principal('a', False))[0]
    assert row['provider'] == 'tajiduo'
    scope = accounts.require_scope(Principal('a', False), row['account_id'], row['roles'][0]['role_id'])
    assert scope.user_id == 'a'
    with pytest.raises(LookupError):
        accounts.require_scope(Principal('b', True), scope.account_id, scope.role_id)
    assert store.load_grant('a', row['grant_id'])['access_token'] == 'token-13800000000'
    assert db.execute('SELECT encrypted_payload FROM grants').fetchone()[0].find(b'token-') == -1


async def test_missing_key_fails_closed(tmp_path):
    db, store, accounts, login = setup(tmp_path)
    await authorize(login)
    row = accounts.list_accounts(Principal('a', False))[0]
    before = db.execute('SELECT encrypted_payload FROM grants').fetchone()[0]
    store.key_path.unlink()
    with pytest.raises(CredentialStoreError):
        store.load_grant('a', row['grant_id'])
    with pytest.raises(CredentialStoreError):
        store.save_grant('a', row['grant_id'], {'access_token': 'new'}, 1)
    assert not store.key_path.exists()
    assert db.execute('SELECT encrypted_payload FROM grants').fetchone()[0] == before


async def test_ciphertext_binds_owner_grant_and_version(tmp_path):
    db, store, accounts, login = setup(tmp_path)
    await authorize(login)
    await authorize(login, 'b', '13900000000')
    rows = db.execute('SELECT grant_id,user_id FROM grants ORDER BY user_id').fetchall()
    body = db.execute('SELECT encrypted_payload FROM grants WHERE user_id="a"').fetchone()[0]
    db.execute('UPDATE grants SET encrypted_payload=? WHERE user_id="b"', (body,))
    with pytest.raises(CredentialStoreError):
        store.load_grant('b', rows[1][0])
    db.execute('UPDATE grants SET version=2 WHERE user_id="a"')
    with pytest.raises(CredentialStoreError):
        store.load_grant('a', rows[0][0])


async def test_logout_invalidates_inflight_renewal(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()

    class Slow(Provider):
        async def renew(self, credentials):
            entered.set()
            await release.wait()
            return {**credentials, 'access_token': 'revived'}

    db, store, accounts, login = setup(tmp_path, Slow())
    await authorize(login)
    row = accounts.list_accounts(Principal('a', False))[0]
    job = asyncio.create_task(login.renew(Principal('a', False), row['grant_id']))
    await entered.wait()
    accounts.revoke(Principal('a', False), row['account_id'])
    release.set()
    with pytest.raises(LoginError):
        await job
    version, state, body = db.execute('SELECT version,state,encrypted_payload FROM grants').fetchone()
    assert (version, state, body) == (2, 'revoked', None)


async def test_relogin_preserves_account_ids_and_advances_version(tmp_path):
    now = [1000]
    db, store, accounts, login = setup(tmp_path,clock=lambda:now[0])
    await authorize(login)
    old = accounts.list_accounts(Principal('a', False))[0]
    accounts.revoke(Principal('a', False), old['account_id'])
    now[0] += 61
    await authorize(login)
    new = accounts.list_accounts(Principal('a', False))[0]
    assert new['account_id'] == old['account_id']
    assert new['roles'][0]['role_id'] == old['roles'][0]['role_id']
    assert new['version'] == 3 and new['state'] == 'active'


async def test_revocation_survives_cleanup_failure_and_is_retryable(tmp_path):
    db, store, accounts, login = setup(tmp_path)
    await authorize(login)
    row = accounts.list_accounts(Principal('a', False))[0]

    def broken(scope):
        raise RuntimeError('cleanup failed')

    accounts.clear_private = broken
    result = accounts.revoke(Principal('a', False), row['account_id'])
    assert result['cleanup_pending']
    with pytest.raises(CredentialStoreError):
        store.load_grant('a', row['grant_id'])
    failed = accounts.list_accounts(Principal('a', False))[0]
    assert failed['version'] == 2 and failed['state'] == 'revoked_cleanup_pending'
    accounts.clear_private = lambda scope: None
    assert not accounts.revoke(Principal('a', False),row['account_id'])['cleanup_pending']
    assert accounts.list_accounts(Principal('a', False))[0]['state'] == 'revoked'


async def test_only_owned_role_can_be_selected(tmp_path):
    db,store,accounts,login = setup(tmp_path)
    await authorize(login)
    await authorize(login,'b','13900000000')
    a,b = [accounts.list_accounts(Principal(u,False))[0] for u in ('a','b')]
    with pytest.raises(LookupError):
        accounts.select_role(Principal('a',False),a['account_id'],b['roles'][0]['role_id'])
    assert accounts.list_accounts(Principal('a',False))[0]['roles'][0]['is_default'] == 1


async def test_hypergryph_and_skland_remain_separately_accessible(tmp_path):
    db,store,accounts,login = setup(tmp_path)
    p = Principal('a',False)
    hg = accounts.save_verified(p,'hypergryph',{'uid':'hg-uid','role_id':'hg-role','server_id':'1','hg_token':'hg-secret'})
    sk = accounts.save_verified(p,'skland',{'user_id':'sk-user','role_id':'sk-role','server_id':'1','cred':'sk-secret'})
    rows = accounts.list_accounts(p)
    assert {r['provider'] for r in rows} == {'hypergryph','skland'}
    assert sum(r['is_default'] for r in rows) == 1
    for result in (hg,sk):
        scope = accounts.require_scope(p,result['account_id'],result['role_id'])
        assert accounts.describe(scope)['state'] == 'active'
    accounts.revoke(p,hg['account_id'])
    assert store.load_grant('a',sk['grant_id'])['cred'] == 'sk-secret'


async def test_routes_use_website_owner_and_redact_validation_input(tmp_path):
    from fastapi import FastAPI
    import httpx
    from game_assistant.accounts.routes import install_account_routes
    from game_assistant.identity.dependencies import require_user
    db,store,accounts,login = setup(tmp_path)
    app = FastAPI()
    owner = [Principal('a',False)]
    app.dependency_overrides[require_user] = lambda: owner[0]
    install_account_routes(app,accounts,login)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        sid = (await client.post('/api/accounts/auth/tajiduo/sessions')).json()['session_id']
        owner[0] = Principal('b',False)
        response = await client.post('/api/accounts/auth/tajiduo/sms',json={'session_id':sid,'mobile':'13800000000'})
        assert response.status_code == 404
        response = await client.post('/api/accounts/auth/skland/connect',json={'cred':'secret-'+ 'x'*4096})
        assert response.status_code == 422 and 'secret-' not in response.text


async def test_logout_invalidates_inflight_login(tmp_path):
    entered,release = asyncio.Event(),asyncio.Event()
    class Slow(Provider):
        async def login(self,*args):
            entered.set()
            await release.wait()
            return await super().login(*args)
    now = [1000]
    db,store,accounts,login = setup(tmp_path,clock=lambda:now[0])
    await authorize(login)
    row = accounts.list_accounts(Principal('a',False))[0]
    login.providers['tajiduo'] = Slow()
    login._contexts[('a','tajiduo')].providers['nte'] = login.providers['tajiduo']
    now[0] += 61
    job = asyncio.create_task(authorize(login))
    await entered.wait()
    accounts.revoke(Principal('a',False),row['account_id'])
    release.set()
    with pytest.raises(LoginError):
        await job
    assert accounts.list_accounts(Principal('a',False))[0]['state'] == 'revoked'
    assert not login._contexts[('a','tajiduo')]._configured('nte')


async def test_verified_skland_roles_preserve_server_scope_and_selection(tmp_path):
    db,store,accounts,login = setup(tmp_path)
    p = Principal('a',False)
    result = accounts.save_verified(p,'skland',{'user_id':'sk-user','role_id':'r1','server_id':'1','cred':'sk-secret',
        'roles':[{'role_id':'r1','server_id':'1'},{'role_id':'r2','server_id':'1'},{'role_id':'r3','server_id':'2'}]})
    rows = accounts.list_accounts(p)
    assert len(rows) == 2
    assert {r['grant_id'] for r in rows} == {result['grant_id']}
    first = next(r for r in rows if r['server']=='1')
    second = next(r for r in rows if r['server']=='2')
    role = next(r for r in first['roles'] if db.execute('SELECT game_uid FROM roles WHERE role_id=?',(r['role_id'],)).fetchone()[0]=='r2')
    accounts.select_role(p,first['account_id'],role['role_id'])
    assert accounts.describe(accounts.require_scope(p,first['account_id'],role['role_id']))['game_uid']=='r2'
    with pytest.raises(LookupError):
        accounts.select_role(p,first['account_id'],second['roles'][0]['role_id'])


async def test_cloud_provider_preserves_verified_roles_without_changing_local_contract():
    import respx
    from tests.test_auth_providers import mock_nte_login
    from game_assistant.auth.providers import NteLoginProvider
    with respx.mock:
        mock_nte_login({'roles':[{'roleId':9001,'roleName':'one'},{'roleId':9002,'roleName':'two'}]})
        result = await NteLoginProvider(include_roles=True).login({'device_id':'HTDEVICE'},'13800000000','123456')
    assert [(r['role_id'],r['server_id']) for r in result['_verified_roles']] == [('9001','official'),('9002','official')]


async def test_direct_grant_save_persists_and_cannot_revive_revoked_grant(tmp_path):
    db,store,accounts,login = setup(tmp_path)
    await authorize(login)
    row = accounts.list_accounts(Principal('a',False))[0]
    filename = tmp_path/'grants.db'
    copied = sqlite3.connect(filename)
    db.backup(copied)
    copied.execute('PRAGMA foreign_keys=ON')
    persistent = CredentialStore(tmp_path/'unused',connection=copied,key_path=store.key_path)
    persistent.save_grant('a',row['grant_id'],{'access_token':'persisted'},1)
    with sqlite3.connect(filename) as other:
        reread = CredentialStore(tmp_path/'unused',connection=other,key_path=store.key_path)
        assert reread.load_grant('a',row['grant_id'])['access_token']=='persisted'
    accounts.revoke(Principal('a',False),row['account_id'])
    with pytest.raises(CredentialStoreError):
        store.save_grant('a',row['grant_id'],{'access_token':'revived'},2)
    copied.close()


def test_endfield_listing_exposes_only_owned_verified_game_uids(tmp_path):
    db, store, accounts, _ = setup(tmp_path)
    principal = Principal('a', False)
    common = {'role_id': '9001', 'server_id': '1', 'channel': 'bilibili', 'nickname': 'same name'}
    accounts.save_verified(principal, 'hypergryph', {**common, 'uid': 'hg-owner', 'hg_token': 'never-expose-hg-token'})
    sk = accounts.save_verified(principal, 'skland', {**common, 'user_id': 'sk-owner', 'cred': 'never-expose-sk-cred'})
    accounts.save_verified(Principal('b', False), 'hypergryph', {**common, 'role_id': 'foreign-role', 'uid': 'other-owner', 'hg_token': 'never-expose-foreign'})
    rows = accounts.list_accounts(principal)
    assert {row['provider'] for row in rows} == {'hypergryph', 'skland'}
    assert [role['game_uid'] for row in rows for role in row['roles']] == ['9001', '9001']
    assert all(role['role_id'] != role['game_uid'] for row in rows for role in row['roles'])
    assert not any(secret in str(rows) for secret in ('never-expose', 'foreign-role', 'hg-owner', 'sk-owner', 'other-owner'))
    # A role removed from the provider's verified response must not return with a UID.
    saved = store.load_grant('a', sk['grant_id'])
    store.save_grant('a', sk['grant_id'], {**saved, 'role_id': 'different', '_verified_roles': [{'role_id': 'different', 'server_id': '1', 'channel': 'bilibili'}]}, 1)
    row = next(row for row in accounts.list_accounts(principal) if row['provider'] == 'skland')
    assert row['roles'] == []
    assert row['state'] == 'role_unavailable'


async def test_other_game_listing_keeps_opaque_role_contract(tmp_path):
    _, _, accounts, login = setup(tmp_path)
    await authorize(login)
    roles = accounts.list_accounts(Principal('a', False))[0]['roles']
    assert set(roles[0]) == {'role_id', 'display_name', 'is_default'}

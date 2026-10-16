"""Reuse only the saved local dashboard Bilibili SESSDATA via trusted SSH stdin.

Default is a read-only configured/decryptable check. --execute is a separately
reviewed operator action; no real secret is accepted in command-line arguments.
"""
import argparse
import base64
import json
import logging
import os
from pathlib import Path,PurePosixPath
import shlex
import subprocess

from scripts.cloud.local_pull import SSHTransport,safe_path
from scripts.cloud import bilibili_migrate_remote as remote

DEFAULT_LOCAL_ROOT='C:/Zcode/game-manage'


class MigrationError(ValueError):pass


def local_sessdata(root):
    from game_assistant.config import Settings
    from game_assistant.auth.store import CredentialStore
    try:
        root=safe_path(root)
        settings=Settings.load(str(root/'config.toml'))
        database=Path(settings.db_path)
        database=database if database.is_absolute() else root/database
        store=safe_path(database.with_suffix('.bilibili.credentials.json'))
        if not store.is_relative_to(root) or not store.is_file():raise ValueError()
        saved=CredentialStore(store).load()
        value=saved.get('bilibili',{}).get('sessdata')
        if not isinstance(value,str) or not value.strip() or len(value)>4096:raise ValueError()
        saved.clear()
        return value
    except Exception:raise MigrationError('local_authorization_unavailable') from None


def transfer(sessdata,transport,remote_python,remote_config):
    python=PurePosixPath(remote_python)
    config=PurePosixPath(remote_config)
    if (not python.is_absolute() or '..' in python.parts or not python.is_relative_to('/opt/game-manage-cloud-trial/releases')
            or python.parts[-3:]!=('.venv','bin','python') or not config.is_absolute()
            or '..' in config.parts or not config.is_relative_to('/etc/game-manage-cloud-trial')):
        raise MigrationError('untrusted_remote_path')
    # Only reviewed program text is encoded into the remote command. The
    # credential is never a shell argument, environment variable or disk file.
    program=Path(remote.__file__).read_bytes()
    encoded=base64.b64encode(program).decode('ascii')
    bootstrap='import base64;exec(compile(base64.b64decode('+repr(encoded)+'),"<reviewed-bilibili-operator>","exec"))'
    command=transport.base+['sudo -n -u game-manage-trial '+shlex.quote(str(python))+' -B -c '+shlex.quote(bootstrap)+' '+shlex.quote(str(config))]
    try:
        result=subprocess.run(command,input=json.dumps({'sessdata':sessdata}).encode('utf-8'),
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=60,
            **({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
        if len(result.stdout)>1024:raise ValueError()
        value=json.loads(result.stdout)
        if result.returncode==0 and value=={'status':'saved','configured':True}:return value
        if (result.returncode==1 and isinstance(value,dict) and set(value)=={'status','error_code'}
                and value['status']=='failed' and value['error_code'] in remote.SAFE_CODES):
            raise MigrationError(value['error_code'])
        raise ValueError()
    except MigrationError:raise
    except Exception:raise MigrationError('remote_result_unconfirmed') from None


def main(argv=None):
    logging.disable(logging.CRITICAL)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-root',default=DEFAULT_LOCAL_ROOT)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--remote-python')
    parser.add_argument('--remote-config')
    args=parser.parse_args(argv)
    value=None
    try:
        value=local_sessdata(args.local_root)
        if not args.execute:
            print(json.dumps({'configured':True,'decryptable':True,'online_validity':'not_checked'}))
            return 0
        if not args.remote_python or not args.remote_config:raise MigrationError('explicit_remote_paths_required')
        result=transfer(value,SSHTransport(),args.remote_python,args.remote_config)
        print(json.dumps(result))
        return 0
    except MigrationError as error:
        print(json.dumps({'status':'failed','error_code':str(error)}))
        return 1
    except Exception:
        print(json.dumps({'status':'failed','error_code':'operator_unavailable'}))
        return 1
    finally:value=None


if __name__=='__main__':raise SystemExit(main())

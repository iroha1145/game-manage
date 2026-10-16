"""Explicit independent bot process; credentials supplied by env or encrypted file."""
import argparse
import asyncio
import logging
import os
from pathlib import Path
import re

from .client import InternalQqClient, OfficialQqClient, QqClientError, load_sdk
from .transport import BotDispatcher, BotState, EventGate
from game_assistant.config import Settings
from game_assistant.paths import through_link


def private_file(path):
    path=Path(path).absolute()
    if through_link(path):raise QqClientError('qq_config_symlink_rejected')
    if not path.is_file():raise QqClientError('qq_config_file_missing')
    if os.name!='nt' and path.stat().st_mode&0o077:raise QqClientError('qq_config_permissions')
    return path


def credentials(path=None):
    if path:
        from game_assistant.auth.store import CredentialStore
        try:config=CredentialStore(private_file(path)).load().get('qq',{})
        except Exception:raise QqClientError('qq_credentials_unavailable') from None
        app_id,secret=config.get('app_id'),config.get('app_secret')
    else:
        app_id,secret=os.environ.get('QQ_BOT_APP_ID'),os.environ.get('QQ_BOT_APP_SECRET')
    if not isinstance(app_id,str) or not app_id.isascii() or not app_id.isdigit() or not isinstance(secret,str) or not secret.strip():
        raise QqClientError('qq_credentials_required')
    return app_id,secret


async def run(args):
    sdk=load_sdk()  # Dependency failure happens before credentials or any HTTP request.
    app_id,secret=credentials(args.credentials_file)
    token=private_file(args.service_token_file).read_text(encoding='utf-8').strip() if args.service_token_file else os.environ.get('QQ_SERVICE_TOKEN','')
    groups=args.allowed_group or [g.strip() for g in os.environ.get('QQ_ALLOWED_GROUPS','').split(',') if g.strip()]
    if not groups or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',g) for g in groups):raise QqClientError('qq_allowed_groups_required')
    if not args.internal_host:raise QqClientError('qq_internal_host_required')
    image_settings=Settings.load()
    service=InternalQqClient(args.internal_url,token,internal_host=args.internal_host,
        images_enabled=image_settings.qq_images_enabled,max_image_bytes=image_settings.qq_image_max_bytes)
    gate=EventGate(app_id,groups,allow_c2c=args.allow_c2c)
    state=BotState(args.state_file)
    dispatcher=BotDispatcher(service,None,state)
    client=OfficialQqClient(app_id,secret,gate,dispatcher,sdk=sdk)
    client.max_image_bytes=image_settings.qq_image_max_bytes
    dispatcher.sender=client
    try:await client.run(duration=args.duration)
    finally:
        await client.aclose()
        await service.aclose()
        state.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Official QQ text bot; separate from cloud API.')
    parser.add_argument('--credentials-file',type=Path,help='Encrypted CredentialStore QQ config; otherwise QQ_BOT_APP_ID/QQ_BOT_APP_SECRET env')
    parser.add_argument('--service-token-file',type=Path,help='Owner-only service token file; otherwise QQ_SERVICE_TOKEN env')
    parser.add_argument('--internal-url',default=os.environ.get('QQ_INTERNAL_URL','http://127.0.0.1:8020'))
    parser.add_argument('--internal-host',default=os.environ.get('QQ_INTERNAL_HOST',''),help='Configured website authority for Host header, e.g. dashboard.example; actual connection stays loopback')
    parser.add_argument('--allowed-group',action='append',help='Explicit OpenID allowlist for this AppID; otherwise QQ_ALLOWED_GROUPS env (comma-separated)')
    parser.add_argument('--allow-c2c',action='store_true',help='Explicitly opt into C2C messages; default group @ only')
    parser.add_argument('--state-file',type=Path,required=True,help='Dedicated bot-state SQLite, separate from game/account databases')
    parser.add_argument('--duration',type=int,help='Bounded real validation window in seconds (5–300)')
    args=parser.parse_args(argv)
    if args.duration is not None and not 5<=args.duration<=300:parser.error('duration must be 5–300')
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    try:asyncio.run(run(args))
    except KeyboardInterrupt:return 0
    except Exception:
        logging.getLogger(__name__).error('QQ bot startup or connection failed; verify dependency, private configuration and platform permissions')
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())

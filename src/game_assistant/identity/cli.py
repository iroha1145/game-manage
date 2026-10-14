"""Local administrative bootstrap/invite/recovery. Password input never echoes.

python -m game_assistant.identity.cli --config config.toml bootstrap-admin
python -m game_assistant.identity.cli --config config.toml invite
python -m game_assistant.identity.cli --config config.toml recovery USER_ID

Protect the cloud DB with OS permissions: this CLI is a trusted local operator
boundary and still verifies the existing admin password for invite/recovery.
"""

import argparse
from getpass import getpass
from pathlib import Path

from game_assistant.config import Settings
from .service import IdentityError, IdentityService
from .store import IdentityStore


def main(argv=None):
    parser = argparse.ArgumentParser(description='Local cloud identity administration')
    parser.add_argument('--config', default='config.toml')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('bootstrap-admin')
    commands.add_parser('invite')
    commands.add_parser('recovery').add_argument('user_id')
    args = parser.parse_args(argv)
    settings = Settings.load(args.config)
    if Path(settings.cloud_db_path).resolve() == Path(settings.db_path).resolve():
        parser.error('Cloud and local database paths must differ')
    service = IdentityService(IdentityStore(settings.cloud_db_path), settings)
    username = input('Admin username: ').strip()
    password = getpass('Admin password: ')
    try:
        if args.command == 'bootstrap-admin':
            if password != getpass('Confirm password: '):
                raise IdentityError('password_confirmation_failed')
            print('Admin user ID:', service.bootstrap_admin(username, password).user_id)
        else:
            session = service.login(username, password, 'local-cli')
            try:
                if args.command == 'invite':
                    print('Invite code:', service.create_invite(session.principal))
                else:
                    print('Recovery code:', service.create_recovery(session.principal, args.user_id))
            finally:
                service.revoke(session.principal, session.session_id)
    except IdentityError as error:
        print('Error:', error.code)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

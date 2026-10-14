"""Isolated game session probes; default is offline and never reads app config/DB."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from probe_common import ROOT, emit, load_config, measure, quiet_logging, save_config, secret_input

FIELDS = {
    'wuwa': ('token', 'b_at', 'did', 'dev_code', 'role_id', 'server_id', 'user_id'),
    'nte': ('access_token', 'refresh_token', 'device_id', 'role_id'),
    'endfield': ('hg_token', 'uid', 'role_id', 'server_id'),
    'skland': ('cred', 'device_id', 'role_id', 'server_id', 'user_id'),
}


def validate(provider, credentials):
    if provider not in FIELDS or not isinstance(credentials, dict):
        raise ValueError('unknown provider')
    for key in FIELDS[provider]:
        value = credentials.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 8192 or any(ord(c) < 32 for c in value):
            raise ValueError('incomplete credentials')
    if provider == 'wuwa' and credentials.get('token_source', 'ios') not in ('ios', 'h5'):
        raise ValueError('invalid token source')
    return credentials


async def query_game(provider, c):
    """Bounded read-only requests; no snapshot DB, sign-in, or refreshData writes."""
    if provider == 'wuwa':
        from game_assistant.adapters.wuthering_waves.kuro_client import KuroClient
        from game_assistant.adapters.wuthering_waves.rolebox_client import RoleBoxClient
        from game_assistant.adapters.wuthering_waves.detail_parse import parse_profile
        client = KuroClient(c['token'], did=c['did'], source=c.get('token_source', 'ios'))
        roles = (await client.role_list()).get('data', [])
        if not any(isinstance(r, dict) and str(r.get('roleId')) == c['role_id']
                   and str(r.get('serverId')) == c['server_id'] for r in roles):
            raise ValueError('selected role not bound')
        async with RoleBoxClient(c['b_at'], c['dev_code'], c['did'], token=c['token']) as rb:
            parse_profile(await rb.base_data(c['role_id'], c['server_id']))
    elif provider == 'nte':
        from game_assistant.adapters.neverness.tajiduo_client import TajiduoClient
        from game_assistant.adapters.neverness.parse import parse_account
        async with TajiduoClient(c['access_token'], device_id=c['device_id']) as client:
            parse_account(await client.get_role_home(c['role_id']), expected_role_id=c['role_id'])
    elif provider == 'endfield':
        from game_assistant.adapters.endfield.hypergryph import HypergryphClient
        from game_assistant.adapters.endfield.parse import select_official_role, record_page
        async with HypergryphClient(trust_env=False) as client:
            grant = await client.grant(c['hg_token'])
            role = select_official_role(await client.binding_list(grant))
            if (role.uid, role.role_id, role.server_id) != (c['uid'], c['role_id'], c['server_id']):
                raise ValueError('selected identity mismatch')
            token = await client.u8_token(c['uid'], grant)
            # One first page, not a history backfill or a claim of complete history.
            rows = await client.char_records(token, 'E_CharacterGachaPoolType_Special')
            record_page(rows, 'char')
    else:
        from game_assistant.adapters.endfield.skland_client import SklandClient
        from game_assistant.adapters.endfield.skland_parse import parse_roles, parse_user_id, parse_card
        client = SklandClient()
        # A transient signature token is mandatory for every Skland query. This
        # is not renewal of cred, nor evidence that natural expiry is handled.
        token = await client.refresh(c['cred'])
        roles = parse_roles(await client.binding(c['cred'], token, c['device_id']))
        user = parse_user_id(await client.user(c['cred'], token, c['device_id']))
        if user != c['user_id'] or not any(r['role_id'] == c['role_id'] and r['server_id'] == c['server_id'] for r in roles):
            raise ValueError('selected identity mismatch')
        card = await client.card(c['cred'], token, c['role_id'], c['server_id'], c['user_id'], c['device_id'])
        parse_card(card, fetched_at=datetime.now(timezone.utc).isoformat())


async def renew_game(provider, credentials):
    from game_assistant.auth.providers import WuwaLoginProvider, NteLoginProvider
    if provider == 'wuwa':
        return await WuwaLoginProvider().renew(credentials)
    if provider == 'nte':
        return await NteLoginProvider().renew(credentials)
    raise ValueError('provider has no session renewal implementation')


async def run_probe(provider, credentials, renew=False, on_renewed=None):
    emit(provider + '.login', 'untested')  # Imported session is not a proven login.
    emit(provider + '.natural_expiry', 'untested')
    current = credentials
    if renew:
        if provider not in ('wuwa', 'nte'):
            emit(provider + '.renewal', 'untested')
            return False
        async def operation():
            nonlocal current
            current = validate(provider, await renew_game(provider, credentials))
            if on_renewed:
                on_renewed(current)  # Persist rotated tokens before query, atomically.
        if not await measure(provider + '.renewal', operation):
            return False
    else:
        emit(provider + '.renewal', 'untested')
    return await measure(provider + '.query', lambda: query_game(provider, current))


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--provider', choices=FIELDS, default='wuwa')
    action = result.add_mutually_exclusive_group()
    action.add_argument('--configure', action='store_true', help='masked import of a human-authorized test session')
    action.add_argument('--validate-config', action='store_true', help='decrypt and validate only')
    action.add_argument('--live', choices=['query', 'renew'], help='explicit live query or rotating-token renewal')
    result.add_argument('--config', type=Path, default=ROOT / '.private-cloud-probes' / 'games.credentials.json')
    result.add_argument('--replace', action='store_true', help='replace this provider only; preserve other providers')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.replace and not args.configure:
        parser().error('--replace requires --configure')
    quiet_logging()
    try:
        if args.configure:
            saved = load_config(args.config) if args.config.exists() else {}
            if args.provider in saved and not args.replace:
                raise FileExistsError('provider already configured')
            credentials = {key: secret_input(key + ': ') for key in FIELDS[args.provider]}
            if args.provider == 'wuwa':
                credentials['token_source'] = 'ios'
            saved[args.provider] = validate(args.provider, credentials)
            save_config(args.config, saved, replace=args.config.exists())
            emit(args.provider + '.configuration', 'passed')
        elif args.validate_config or args.live:
            saved = load_config(args.config)
            credentials = validate(args.provider, saved.get(args.provider))
            if args.validate_config:
                emit(args.provider + '.configuration', 'passed')
            else:
                def persist(updated):
                    saved[args.provider] = updated
                    save_config(args.config, saved, replace=True)
                return 0 if asyncio.run(run_probe(args.provider, credentials, renew=args.live == 'renew',
                                                   on_renewed=persist)) else 1
        else:
            for provider in FIELDS:
                for step in ('login', 'query', 'natural_expiry', 'renewal'):
                    emit(provider + '.' + step, 'untested')
        return 0
    except (Exception, KeyboardInterrupt) as error:
        emit('games.probe', 'failed', error_type=type(error).__name__)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

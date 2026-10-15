"""Minimal QQ probe. Default: no credential reads, no network, no messages."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import re

from probe_common import ROOT, emit, load_config, measure, quiet_logging, save_config, secret_input

API_BASE = 'https://api.bot.qq.com'
SDK_CANDIDATE = 'qqbot-agent-sdk'
SDK_VERSION = '1.2.2'  # Probe candidate only; NOT a live-compatible product lock.


def validate(config):
    for key in ('app_id', 'app_secret', 'environment'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError('invalid QQ configuration')
    if not config['app_id'].isascii() or not config['app_id'].isdigit():
        raise ValueError('invalid app ID')
    if config.get('test_group') and not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', config['test_group']):
        raise ValueError('invalid test group OpenID')
    if config['environment'] not in ('sandbox', 'production'):
        raise ValueError('invalid environment')
    return config


async def get_token(client, config):
    response = await client.post(API_BASE + '/app/getAppAccessToken',
                                 json={'appId': config['app_id'], 'clientSecret': config['app_secret']})
    if response.status_code != 200:
        raise RuntimeError('token request rejected')
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get('access_token'), str) or not data['access_token']:
        raise ValueError('invalid token response')
    if isinstance(data.get('expires_in'), bool) or not 1 <= int(data.get('expires_in', 0)) <= 7200:
        raise ValueError('invalid token expiry')
    return data['access_token']


async def get_gateway(client, token):
    response = await client.get(API_BASE + '/gateway', headers={'Authorization': f'QQBot {token}'})
    if response.status_code != 200:
        raise RuntimeError('gateway request rejected')
    data = response.json()
    url = data.get('url') if isinstance(data, dict) else None
    if not isinstance(url, str) or not url.startswith('wss://'):
        raise ValueError('invalid gateway response')
    return url


class GroupProbe:
    """No unsolicited sends; one canned passive reply to /probe in one group."""
    def __init__(self, group, reply, send, discover=False):
        self.group, self.reply, self.send = group, reply, send
        self.discover = discover
        self.seen = set()
        self.received = self.replied = 0

    async def handle(self, event_type, data):
        if event_type != 'GROUP_AT_MESSAGE_CREATE':
            return
        if self.discover:
            group = data.get('group_openid')
            if isinstance(group, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', group) and group not in self.seen:
                self.seen.add(group)
                self.received += 1
                print(json.dumps({'step': 'qq.discovery', 'status': 'passed', 'elapsed_ms': 0,
                                  'group_openid': group}), flush=True)
            return
        if data.get('group_openid') != self.group:
            return
        message_id = data.get('id')
        content = data.get('content')
        if not isinstance(message_id, str) or not message_id or not isinstance(content, str):
            return
        command = re.sub(r'^<@!?\d+>\s*', '', content.strip())
        if command != '/probe' or message_id in self.seen or len(self.seen) >= 1024:
            return
        self.seen.add(message_id)  # Before sending; a failed send is never blindly retried.
        self.received += 1
        emit('qq.receive', 'passed')
        if self.reply:
            await self.send(self.group, {'content': '探针测试成功', 'msg_type': 0,
                                         'msg_id': message_id, 'msg_seq': 1})
            self.replied += 1
            emit('qq.reply', 'passed')


def require_sdk_runtime():
    # These imports are lazy in SDK 1.2.2. In particular a missing aiohttp is
    # otherwise swallowed by its WS thread and looks like a platform timeout.
    from importlib import import_module
    for dependency in ('aiohttp', 'httpx', 'cryptography'):
        try:
            import_module(dependency)
        except Exception as error:
            emit('qq.dependency.' + dependency, 'failed', error_type=type(error).__name__)
            raise RuntimeError('SDK runtime dependency unavailable') from None


async def receive(config, gateway, duration, reply, discover=False, handshake_only=False):
    # Optional SDK import only inside explicitly requested live receive.
    require_sdk_runtime()
    from importlib.metadata import version
    if version(SDK_CANDIDATE) != SDK_VERSION:
        raise RuntimeError('candidate SDK version mismatch')
    from qqbot_agent_sdk import QQApiClient, QQWebSocket, WSCallbacks
    import qqbot_agent_sdk.api_client as sdk_http
    # Both current official endpoints differ from SDK 1.2.2 defaults.
    sdk_http.API_BASE = API_BASE
    sdk_http.TOKEN_URL = API_BASE + '/app/getAppAccessToken'
    import httpx
    connected = asyncio.Event()
    fatal = asyncio.Event()
    loop = asyncio.get_running_loop()
    session = [None, None]
    connects = [0]
    async with httpx.AsyncClient(timeout=20, trust_env=False) as http:
        api = QQApiClient(config['app_id'], config['app_secret'])
        api.setup(http)
        async def send(group, body):
            await api.request('POST', f'/v2/groups/{group}/messages', body)
        gate = GroupProbe(config.get('test_group', ''), reply, send, discover=discover)
        async def handle(kind, data):
            try:
                await gate.handle(kind, data)
            except Exception as error:
                emit('qq.reply', 'failed', error_type=type(error).__name__)
                loop.call_soon_threadsafe(fatal.set)
        def on_connected():
            connects[0] += 1
            emit('qq.handshake' if connects[0] == 1 else 'qq.reconnect', 'passed')
            loop.call_soon_threadsafe(connected.set)
        def on_fatal(code, message):
            emit('qq.websocket', 'failed', error_type='GatewayError')
            loop.call_soon_threadsafe(fatal.set)
        callbacks = WSCallbacks(on_message_event=handle, on_connected=on_connected,
            on_disconnected=lambda: emit('qq.disconnect', 'passed'), on_fatal_error=on_fatal,
            get_token=api.ensure_token_sync, get_session=lambda: tuple(session),
            set_session=lambda sid, seq: session.__setitem__(slice(None), [sid, seq]),
            set_heartbeat_interval=lambda seconds: None, clear_token=api.clear_token,
            fail_pending=lambda reason: None, get_gateway_url=api.get_gateway_url_sync,
            on_heartbeat_ack=lambda: emit('qq.heartbeat', 'passed'))
        ws = QQWebSocket(callbacks=callbacks, log_tag='probe')
        ws.start(gateway, loop)
        try:
            await asyncio.wait_for(fatal.wait(), timeout=duration)
        except asyncio.TimeoutError:
            pass
        finally:
            await ws.async_stop()
        if not connected.is_set():
            emit('qq.handshake', 'failed', error_type='NotObserved')
        if not gate.received:
            emit('qq.receive', 'untested')
        if reply and not gate.replied:
            emit('qq.reply', 'untested')
        if connects[0] < 2:
            emit('qq.reconnect', 'untested')
        emit('qq.token_natural_renewal', 'untested')
        emit('qq.live_duplicate_delivery', 'untested')
        if fatal.is_set() or not connected.is_set() or (not handshake_only and not gate.received) or (reply and not gate.replied):
            raise RuntimeError('live receive incomplete')


async def live(config, step, duration, reply):
    if step in ('handshake', 'receive', 'discover'):
        require_sdk_runtime()  # Fail before network/token requests if setup is incomplete.
    import httpx
    async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
        token = await get_token(client, config)
        emit('qq.token', 'passed')
        if step == 'token':
            return
        gateway = await get_gateway(client, token)
        emit('qq.gateway', 'passed')
        if step in ('handshake', 'receive', 'discover'):
            await receive(config, gateway, duration, reply, discover=step == 'discover', handshake_only=step == 'handshake')


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    action = result.add_mutually_exclusive_group()
    action.add_argument('--configure', action='store_true', help='masked local configuration; never contacts QQ')
    action.add_argument('--validate-config', action='store_true', help='decrypt and validate only; no network')
    action.add_argument('--live', choices=['token', 'gateway', 'handshake', 'discover', 'receive'], help='explicit network permission; handshake requires no group and never replies; discover prints only group OpenID')
    result.add_argument('--config', type=Path, default=ROOT / '.private-cloud-probes' / 'qq.credentials.json')
    result.add_argument('--replace', action='store_true', help='explicitly replace existing local configuration')
    result.add_argument('--duration', type=int, default=60, help='bounded receive duration, 5..300 seconds')
    result.add_argument('--reply-test', action='store_true', help='reply only to @ /probe in configured test group')
    result.add_argument('--group-openid', help='selected test group OpenID for receive; never use QQ group number')
    result.add_argument('--environment', choices=['sandbox', 'production'], default='sandbox',
                        help='console environment label; does not configure platform sandbox')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    if args.reply_test and args.live != 'receive':
        parser().error('--reply-test requires --live receive')
    if not 5 <= args.duration <= 300 or (args.replace and not args.configure):
        parser().error('invalid duration or --replace without --configure')
    quiet_logging()
    try:
        if args.configure:
            config = {'app_id': secret_input('AppID: '), 'app_secret': secret_input('AppSecret: '),
                      'environment': args.environment}
            save_config(args.config, {'qq': validate(config)}, replace=args.replace)
            emit('qq.configuration', 'passed')
        elif args.validate_config or args.live:
            config = validate(load_config(args.config).get('qq', {}))
            if args.group_openid:
                config = validate({**config, 'test_group': args.group_openid})
            if args.live == 'receive' and not config.get('test_group'):
                raise ValueError('selected test group required')
            if args.live == 'discover' and config['environment'] != 'sandbox':
                raise ValueError('discovery requires sandbox test configuration')
            if args.validate_config:
                emit('qq.configuration', 'passed')
            else:
                return 0 if asyncio.run(measure('qq.live', lambda: live(config, args.live, args.duration, args.reply_test),
                                               timeout=args.duration + 90)) else 1
        else:
            for step in ('configuration', 'token', 'gateway', 'handshake', 'heartbeat', 'receive', 'reply',
                         'reconnect', 'token_natural_renewal', 'live_duplicate_delivery'):
                emit('qq.' + step, 'untested')
        return 0
    except (Exception, KeyboardInterrupt) as error:
        emit('qq.probe', 'failed', error_type=type(error).__name__)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Offline safety and protocol-boundary tests; no real credentials or QQ traffic."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'cloud'))


def module(name):
    path = ROOT / 'scripts' / 'cloud' / f'{name}.py'
    assert path.exists(), 'probe implementation missing'
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('name', ['probe_qq', 'probe_games'])
def test_default_run_does_not_read_credentials_or_contact_network(name, tmp_path):
    script = ROOT / 'scripts' / 'cloud' / f'{name}.py'
    assert script.exists(), 'probe implementation missing'
    result = subprocess.run([sys.executable, str(script), '--config', str(tmp_path / 'missing.credentials.json')],
                            capture_output=True, text=True)
    assert result.returncode == 0
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert rows and all(row['status'] == 'untested' for row in rows)
    assert not list(tmp_path.iterdir())


def test_encrypted_configuration_round_trip_and_refuses_overwrite(tmp_path):
    common = module('probe_common')
    path = tmp_path / '.private-cloud-probes' / 'qq.credentials.json'
    secret = 'offline-test-secret-NEVER-log'
    common.save_config(path, {'qq': {'app_id': '123', 'app_secret': secret}})
    assert secret.encode() not in path.read_bytes()
    assert common.load_config(path)['qq']['app_secret'] == secret
    with pytest.raises(FileExistsError):
        common.save_config(path, {'qq': {'app_secret': 'replacement'}})
    assert common.load_config(path)['qq']['app_secret'] == secret


def test_config_rejects_arbitrary_existing_parent_before_permission_change(tmp_path, monkeypatch):
    common = module('probe_common')
    documents = tmp_path / 'Documents'
    documents.mkdir()
    def forbidden(*args, **kwargs):
        pytest.fail('arbitrary directory permissions must never change')
    monkeypatch.setattr(common, 'owner_only', forbidden)
    with pytest.raises(ValueError):
        common.save_config(documents / 'qq.credentials.json', {'qq': {'app_secret': 'PRIVATE'}})
    assert list(documents.iterdir()) == []


def test_masked_configuration_rejects_noninteractive_input(monkeypatch):
    common = module('probe_common')
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    with pytest.raises(ValueError):
        common.secret_input('AppSecret: ')


@pytest.mark.asyncio
async def test_qq_token_uses_current_domain_and_never_reports_upstream_secrets():
    qq = module('probe_qq')
    async def handler(request):
        assert str(request.url) == 'https://api.bot.qq.com/app/getAppAccessToken'
        assert json.loads(request.content) == {'appId': '123', 'clientSecret': 'PRIVATE'}
        return httpx.Response(200, json={'access_token': 'TOKEN', 'expires_in': '7200'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await qq.get_token(client, {'app_id': '123', 'app_secret': 'PRIVATE'}) == 'TOKEN'
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401, text='PRIVATE TOKEN'))) as client:
        with pytest.raises(Exception) as caught:
            await qq.get_token(client, {'app_id': '123', 'app_secret': 'PRIVATE'})
    assert 'PRIVATE' not in str(caught.value) and 'TOKEN' not in str(caught.value)


@pytest.mark.asyncio
async def test_qq_reply_only_selected_group_command_once():
    qq = module('probe_qq')
    sent = []
    async def send(group, message):
        sent.append((group, message))
    gate = qq.GroupProbe('selected', True, send)
    event = {'group_openid': 'other', 'id': 'm1', 'content': '/probe'}
    await gate.handle('GROUP_AT_MESSAGE_CREATE', event)
    event['group_openid'] = 'selected'
    await gate.handle('GROUP_MESSAGE_CREATE', event)
    event['content'] = 'ordinary chat'
    await gate.handle('GROUP_AT_MESSAGE_CREATE', event)
    event['content'] = '<@!123> /probe'
    await gate.handle('GROUP_AT_MESSAGE_CREATE', event)
    await gate.handle('GROUP_AT_MESSAGE_CREATE', event)
    assert len(sent) == 1
    assert sent[0] == ('selected', {'content': '探针测试成功', 'msg_type': 0, 'msg_id': 'm1', 'msg_seq': 1})
    assert gate.received == 1 and gate.replied == 1


@pytest.mark.asyncio
async def test_receive_mode_never_sends_without_explicit_reply_flag():
    qq = module('probe_qq')
    async def forbidden(*args):
        pytest.fail('receive-only must never send')
    gate = qq.GroupProbe('selected', False, forbidden)
    await gate.handle('GROUP_AT_MESSAGE_CREATE', {'group_openid': 'selected', 'id': 'id', 'content': '/probe'})
    assert gate.received == 1 and gate.replied == 0


def test_game_config_requires_distinct_endfield_and_skland_credentials():
    games = module('probe_games')
    with pytest.raises(ValueError):
        games.validate('skland', {'hg_token': 'NOT-SKLAND'})
    with pytest.raises(ValueError):
        games.validate('endfield', {'cred': 'NOT-HYPERGRYPH'})


@pytest.mark.asyncio
async def test_game_failure_reports_only_controlled_type(capsys):
    common = module('probe_common')
    async def fail():
        raise RuntimeError('cookie=SECRET; account=PRIVATE')
    passed = await common.measure('query', fail)
    assert not passed
    row = json.loads(capsys.readouterr().out)
    assert row['status'] == 'failed' and row['error_type'] == 'RuntimeError'
    assert 'SECRET' not in str(row) and 'PRIVATE' not in str(row)


@pytest.mark.asyncio
async def test_game_read_only_probe_does_not_renew_or_overwrite(tmp_path, monkeypatch, capsys):
    games = module('probe_games')
    credentials = {'access_token': 'ACCESS', 'refresh_token': 'REFRESH', 'device_id': 'D', 'role_id': 'R'}
    async def query(provider, account):
        assert provider == 'nte' and account == credentials
    async def forbidden(*args):
        pytest.fail('read-only query cannot rotate credentials')
    monkeypatch.setattr(games, 'query_game', query)
    monkeypatch.setattr(games, 'renew_game', forbidden)
    assert await games.run_probe('nte', credentials, renew=False)
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert next(row for row in rows if row['step'] == 'nte.query')['status'] == 'passed'
    assert next(row for row in rows if row['step'] == 'nte.renewal')['status'] == 'untested'


def test_qq_credential_only_configuration_validates_without_group():
    qq = module('probe_qq')
    assert qq.validate({'app_id': '123', 'app_secret': 'PRIVATE', 'environment': 'sandbox'})


@pytest.mark.asyncio
async def test_group_discovery_does_not_send_or_expose_member_and_text(capsys):
    qq = module('probe_qq')
    async def forbidden(*args):
        pytest.fail('discovery cannot send')
    gate = qq.GroupProbe('', False, forbidden, discover=True)
    await gate.handle('GROUP_AT_MESSAGE_CREATE', {'group_openid': 'GROUPID', 'id': 'm1',
                    'content': '/probe PRIVATE', 'author': {'member_openid': 'MEMBER'}})
    output = capsys.readouterr().out
    assert 'GROUPID' in output and 'MEMBER' not in output and 'PRIVATE' not in output


@pytest.mark.asyncio
async def test_wuwa_query_imports_profile_parser_and_rejects_wrong_role(monkeypatch):
    games = module('probe_games')
    from game_assistant.adapters.wuthering_waves.kuro_client import KuroClient
    async def wrong_role(self):
        return {'code': 200, 'data': [{'roleId': 'OTHER', 'serverId': 'S'}]}
    monkeypatch.setattr(KuroClient, 'role_list', wrong_role)
    with pytest.raises(ValueError, match='selected role not bound'):
        await games.query_game('wuwa', {'token': 'T', 'did': 'D', 'token_source': 'ios', 'role_id': 'R', 'server_id': 'S'})


@pytest.mark.asyncio
@pytest.mark.parametrize('malformed', [False, True])
async def test_endfield_query_reads_one_official_pool_page(monkeypatch, malformed):
    games = module('probe_games')
    from game_assistant.adapters.endfield.data_models import EndfieldRole
    from game_assistant.adapters.endfield import parse
    requested = []
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def grant(self, token): return 'GRANT'
        async def binding_list(self, token): return {}
        async def u8_token(self, uid, token): return 'U8'
        async def char_records(self, token, pool):
            requested.append(pool)
            return {'unexpected': 'response'} if malformed else {'list': [], 'hasMore': False}
    monkeypatch.setattr('game_assistant.adapters.endfield.hypergryph.HypergryphClient', lambda **kw: Client())
    monkeypatch.setattr(parse, 'select_official_role', lambda data: EndfieldRole(uid='U', role_id='R', server_id='S'))
    credentials = {'hg_token': 'H', 'uid': 'U', 'role_id': 'R', 'server_id': 'S'}
    if malformed:
        with pytest.raises(ValueError):
            await games.query_game('endfield', credentials)
    else:
        await games.query_game('endfield', credentials)
    assert requested == ['E_CharacterGachaPoolType_Special']


@pytest.mark.asyncio
async def test_renewed_credentials_are_persisted_before_query_and_old_input_preserved(monkeypatch, capsys):
    games = module('probe_games')
    old = {'access_token': 'OLD', 'refresh_token': 'OLDREF', 'device_id': 'D', 'role_id': 'R'}
    state = {}
    async def renew(provider, account):
        return {**account, 'access_token': 'NEW', 'refresh_token': 'NEWREF'}
    async def query(provider, account):
        assert state['saved']['access_token'] == account['access_token'] == 'NEW'
        raise RuntimeError('private upstream detail')
    monkeypatch.setattr(games, 'renew_game', renew)
    monkeypatch.setattr(games, 'query_game', query)
    assert not await games.run_probe('nte', old, renew=True, on_renewed=lambda c: state.update(saved=c))
    assert old['access_token'] == 'OLD'
    assert 'NEWREF' not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_failed_renewal_never_overwrites_valid_configuration(monkeypatch, capsys):
    games = module('probe_games')
    async def renew(*args):
        raise RuntimeError('private failure')
    def forbidden(*args):
        pytest.fail('failed renewal cannot persist')
    monkeypatch.setattr(games, 'renew_game', renew)
    assert not await games.run_probe('nte', {}, renew=True, on_renewed=forbidden)


@pytest.mark.parametrize('flags', [['--reply-test'], ['--replace'], ['--duration', '999']])
def test_unsafe_qq_cli_flags_fail_before_credentials_read(flags, tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/cloud/probe_qq.py'),
                             '--config', str(tmp_path / 'missing.credentials.json'), *flags],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert not list(tmp_path.iterdir())


def test_missing_websocket_dependency_fails_immediately_without_secret_detail(monkeypatch, capsys):
    qq = module('probe_qq')
    import importlib
    real_import = importlib.import_module
    def dependency_import(name, *args, **kwargs):
        if name == 'aiohttp':
            raise ModuleNotFoundError('private upstream/path detail')
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(importlib, 'import_module', dependency_import)
    with pytest.raises(RuntimeError):
        qq.require_sdk_runtime()
    output = capsys.readouterr().out
    assert 'qq.dependency.aiohttp' in output and 'ModuleNotFoundError' in output
    assert 'private' not in output


def test_handshake_only_cli_requires_no_group_and_never_enables_reply(monkeypatch):
    import logging
    qq = module('probe_qq')
    monkeypatch.setattr(qq, 'load_config', lambda path: {'qq': {'app_id': '123', 'app_secret': 'PRIVATE', 'environment': 'sandbox'}})
    observed = []
    async def live(config, step, duration, reply):
        observed.append((step, reply, config.get('test_group')))
    monkeypatch.setattr(qq, 'live', live)
    # The real probe silences all logs for its dedicated process to protect
    # credentials. This in-process test must restore that global state.
    previous_disable = logging.root.manager.disable
    try:
        assert qq.main(['--live', 'handshake', '--duration', '5']) == 0
    finally:
        logging.disable(previous_disable)
    assert observed == [('handshake', False, None)]

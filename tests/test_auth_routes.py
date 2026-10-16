import pytest
from fastapi.testclient import TestClient

from game_assistant.api import create_app
from game_assistant.auth.providers import AuthError
from game_assistant.auth.service import LoginService
from game_assistant.auth.store import CredentialStore
from game_assistant.config import Settings
from game_assistant.snapshots import SnapshotStore
from tests.test_auth_service import Provider


def client_for(tmp_path):
    settings = Settings(db_path=str(tmp_path / 'test.db'),
                        auth_allowed_origins=['http://testserver'])
    provider = Provider()
    service = LoginService(settings, CredentialStore(tmp_path / 'credentials'),
                           providers={'nte': provider, 'wuthering_waves': provider})
    snapshots = SnapshotStore(settings.db_path)
    app = create_app(settings=settings, store=snapshots, auth_service=service,
                     start_scheduler=False)
    return TestClient(app), service, snapshots, provider


HEADERS = {'X-Game-Assistant': '1'}


def test_auth_writes_reject_missing_header_and_cross_origin(tmp_path):
    client, _, _, provider = client_for(tmp_path)
    assert client.post('/api/auth/nte/sessions').status_code == 403
    assert client.post('/api/auth/nte/sessions', headers={**HEADERS, 'Origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/auth/nte/sessions', headers={**HEADERS, 'Host': 'evil.example'}).status_code == 403
    assert provider.started == 0


def test_real_router_login_clears_private_snapshots_and_hot_updates(tmp_path):
    client, service, store, provider = client_for(tmp_path)
    store.save('nte', 'roles', '[{"name":"old account"}]')
    store.save('nte', 'announcement', '[]')
    sid = client.post('/api/auth/nte/sessions', headers=HEADERS).json()['session_id']
    body = {'session_id': sid, 'mobile': '13800000000'}
    assert client.post('/api/auth/nte/sms', headers=HEADERS, json=body).status_code == 200
    result = client.post('/api/auth/nte/login', headers=HEADERS, json={**body, 'code': '123456'})
    assert result.status_code == 200
    assert result.json()['account']['configured']
    assert 'secret' not in result.text
    assert store.get('nte', 'roles') is None
    assert store.get('nte', 'announcement') is not None
    nte = next(g for g in client.get('/api/games').json() if g['game_id'] == 'nte')
    assert nte['credentials_configured']
    assert client.delete('/api/auth/nte', headers=HEADERS).status_code == 200
    assert not service.registry.get('nte').credentials_configured


def test_validation_errors_do_not_echo_phone_or_code_and_responses_are_no_store(tmp_path):
    client, _, _, _ = client_for(tmp_path)
    result = client.post('/api/auth/nte/login', headers=HEADERS,
                         json={'mobile': '13800000000', 'code': {'secret': '123456'}})
    assert result.status_code == 422
    assert '13800000000' not in result.text and '123456' not in result.text
    assert result.headers['cache-control'] == 'no-store'
    assert client.get('/api/auth/status').headers['cache-control'] == 'no-store'


def test_unknown_game_and_expired_session_have_clear_status_codes(tmp_path):
    client, _, _, _ = client_for(tmp_path)
    assert client.post('/api/auth/nope/sessions', headers=HEADERS).status_code == 404
    result = client.post('/api/auth/nte/sms', headers=HEADERS,
                         json={'session_id': 'expired', 'mobile': '13800000000'})
    assert result.status_code == 410


def test_snapshot_cleanup_failure_does_not_commit_login(tmp_path, monkeypatch):
    import sqlite3
    client, service, store, provider = client_for(tmp_path)
    def locked(game):
        raise sqlite3.OperationalError('locked')
    monkeypatch.setattr(store, 'clear_private', locked)
    sid = client.post('/api/auth/nte/sessions', headers=HEADERS).json()['session_id']
    body = {'session_id': sid, 'mobile': '13800000000'}
    client.post('/api/auth/nte/sms', headers=HEADERS, json=body)
    response = client.post('/api/auth/nte/login', headers=HEADERS, json={**body, 'code': '123456'})
    assert response.status_code == 500
    assert not service.status()['accounts']['nte']['configured']
    assert service.store.load() == {}


def test_login_body_limit_counts_chunked_bodies(tmp_path):
    client, _, _, provider = client_for(tmp_path)
    sid = client.post('/api/auth/nte/sessions', headers=HEADERS).json()['session_id']
    body = ('{"session_id":"%s","mobile":"13800000000","captcha":{"pad":"%s"}}' % (sid, 'a' * 20000)).encode()
    headers = {**HEADERS, 'Content-Type': 'application/json'}
    sized = client.post('/api/auth/nte/sms', headers=headers, content=body)
    # A generator body is sent with Transfer-Encoding: chunked and no Content-Length.
    chunked = client.post('/api/auth/nte/sms', headers=headers,
                          content=(body[i:i + 4096] for i in range(0, len(body), 4096)))
    assert sized.status_code == chunked.status_code == 413
    assert chunked.json() == {'detail': '登录请求过大'}
    assert provider.sent == 0


class RejectingProvider(Provider):
    """Fails one login step the way the real providers do: AuthError with the upstream code."""
    def __init__(self, step, code):
        super().__init__()
        self.step, self.code = step, code

    async def send_sms(self, context, mobile, captcha=None):
        if self.step == 'sms':
            raise AuthError('上游拒绝了请求', self.code)
        await super().send_sms(context, mobile, captcha)

    async def login(self, context, mobile, code):
        raise AuthError('上游拒绝了请求', self.code)


@pytest.mark.parametrize('step,code,status', [('sms', 429, 429), ('login', 429, 429),
                                              ('sms', 270, 400), ('login', 130, 400)])
def test_only_an_upstream_rate_limit_keeps_its_429_status(tmp_path, step, code, status):
    client, service, _, _ = client_for(tmp_path)
    service.providers['nte'] = RejectingProvider(step, code)
    sid = client.post('/api/auth/nte/sessions', headers=HEADERS).json()['session_id']
    body = {'session_id': sid, 'mobile': '13800000000'}
    response = client.post('/api/auth/nte/sms', headers=HEADERS, json=body)
    if step == 'login':
        assert response.status_code == 200
        response = client.post('/api/auth/nte/login', headers=HEADERS, json={**body, 'code': '123456'})
    assert response.status_code == status
    assert response.json() == {'detail': '上游拒绝了请求'}
    # The login page starts its cooldown on 429 and reads Retry-After, as for the local limiter.
    assert response.headers.get('retry-after') == ('60' if status == 429 else None)

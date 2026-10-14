import sqlite3

import pytest
from fastapi.testclient import TestClient

from game_assistant.cloud_app import create_cloud_app
from game_assistant.config import Settings
from game_assistant.identity.service import IdentityService, IdentityError
from game_assistant.identity.store import IdentityStore


@pytest.fixture
def identity(tmp_path):
    settings = Settings(cloud_db_path=str(tmp_path / 'cloud.db'),
                        cloud_allowed_origins=['https://cloud.example'])
    service = IdentityService(IdentityStore(settings.cloud_db_path), settings)
    admin = service.bootstrap_admin('admin', 'Admin-password-123')
    client = TestClient(create_cloud_app(settings, start_scheduler=False),
                        base_url='https://cloud.example')
    return settings, service, admin, client


def write(client, path, payload=None, method='post'):
    csrf = client.get('/api/identity/csrf').json()['csrf_token']
    return client.request(method.upper(), path, json=payload, headers={'X-CSRF-Token': csrf})


def register(identity, username='alice'):
    _, service, admin, client = identity
    invite = service.create_invite(admin)
    response = write(client, '/api/identity/register',
                     {'username': username, 'password': 'Password-alice-123', 'invite': invite})
    assert response.status_code == 200
    return response.json()


def test_invite_is_single_use(identity):
    _, service, admin, client = identity
    invite = service.create_invite(admin)
    payload = {'username': 'alice', 'password': 'Password-alice-123', 'invite': invite}
    assert write(client, '/api/identity/register', payload).status_code == 200
    payload['username'] = 'bob'
    assert write(client, '/api/identity/register', payload).status_code == 400


def test_login_rotates_session(identity):
    register(identity)
    _, service, _, client = identity
    old = client.cookies.get('__Host-ga_session')
    assert write(client, '/api/identity/login',
                 {'username': 'alice', 'password': 'Password-alice-123'}).status_code == 200
    new = client.cookies.get('__Host-ga_session')
    assert old != new
    assert service.authenticate(old) is None
    assert service.authenticate(new) is not None


def test_csrf_required_for_write(identity):
    client = identity[3]
    assert client.post('/api/identity/login', json={}).status_code == 401
    client.get('/api/identity/csrf')
    assert client.post('/api/identity/login', json={}).status_code == 403
    assert client.get('/api/identity/me').status_code == 401
    register(identity)
    assert client.post('/api/identity/logout').status_code == 403
    assert write(client, '/api/identity/logout').status_code == 200
    assert client.get('/api/identity/me').status_code == 401


def test_recovery_revokes_sessions(identity):
    data = register(identity)
    _, service, admin, client = identity
    old = client.cookies.get('__Host-ga_session')
    recovery = service.create_recovery(admin, data['user_id'])
    payload = {'recovery': recovery, 'password': 'New-password-12345'}
    assert write(client, '/api/identity/recover', payload).status_code == 200
    assert service.authenticate(old) is None
    assert write(client, '/api/identity/recover', payload).status_code == 400
    assert write(client, '/api/identity/login',
                 {'username': 'alice', 'password': 'New-password-12345'}).status_code == 200


def test_session_revoke_cannot_target_other_user(identity):
    register(identity)
    settings, _, _, client = identity
    alice = client.get('/api/identity/sessions').json()['sessions'][0]['session_id']
    register(identity, 'bob')
    response = write(client, '/api/identity/sessions/' + alice, method='delete')
    assert response.status_code == 404
    assert client.get('/api/identity/me').status_code == 200


def test_password_and_tokens_are_not_stored_plaintext(identity):
    register(identity)
    settings, _, _, client = identity
    cookie = client.cookies.get('__Host-ga_session')
    response = client.get('/api/identity/csrf')
    csrf = response.json()['csrf_token']
    with sqlite3.connect(settings.cloud_db_path) as db:
        password_hash = db.execute("SELECT password_hash FROM users WHERE username='alice'").fetchone()[0]
        assert password_hash.startswith('$argon2id$')
        serialized = str(db.execute('SELECT * FROM sessions').fetchall())
        assert cookie not in serialized and csrf not in serialized
    header = write(client, '/api/identity/login',
                   {'username': 'alice', 'password': 'Password-alice-123'}).headers['set-cookie']
    assert 'Secure' in header and 'HttpOnly' in header and 'SameSite=lax' in header


def test_rate_limits_persist_and_apply_to_account_and_ip(identity):
    settings, service, _, _ = identity
    for number in range(10):
        with pytest.raises(IdentityError) as error:
            service.login('admin', 'wrong-password', f'192.0.2.{number}')
        assert error.value.status_code == 401
    restarted = IdentityService(IdentityStore(settings.cloud_db_path), settings)
    with pytest.raises(IdentityError) as error:
        restarted.login('ADMIN', 'Admin-password-123', '192.0.2.99')
    assert error.value.status_code == 429
    for number in range(10):
        with pytest.raises(IdentityError):
            restarted.login(f'unknown{number}', 'wrong-password', '192.0.2.200')
    with pytest.raises(IdentityError) as error:
        restarted.login('some-other', 'wrong-password', '192.0.2.200')
    assert error.value.status_code == 429


def test_bootstrap_is_local_single_initial_admin(identity):
    with pytest.raises(IdentityError):
        identity[1].bootstrap_admin('second', 'Another-password-123')
    assert identity[3].post('/api/identity/bootstrap').status_code == 404


def test_expired_and_disabled_sessions_fail(identity):
    register(identity)
    settings, _, _, client = identity
    with sqlite3.connect(settings.cloud_db_path) as db:
        db.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00.000000Z'")
    assert client.get('/api/identity/me').status_code == 401
    assert write(client, '/api/identity/login', {'username': 'alice', 'password': 'Password-alice-123'}).status_code == 200
    with sqlite3.connect(settings.cloud_db_path) as db:
        db.execute("UPDATE users SET disabled_at='2026-01-01' WHERE username='alice'")
    assert client.get('/api/identity/me').status_code == 401


def test_invalid_requests_do_not_echo_password(identity):
    response = write(identity[3], '/api/identity/login', {'username': {}, 'password': 'TOP_SECRET'})
    assert response.status_code == 422
    assert 'TOP_SECRET' not in response.text


def test_expired_invites_and_recoveries_do_not_change_password(identity):
    settings, service, admin, client = identity
    invite = service.create_invite(admin)
    with sqlite3.connect(settings.cloud_db_path) as db:
        db.execute("UPDATE invites SET expires_at='2000-01-01T00:00:00Z'")
    assert write(client, '/api/identity/register', {'username': 'alice', 'password': 'Password-alice-123', 'invite': invite}).status_code == 400
    data = register(identity)
    recovery = service.create_recovery(admin, data['user_id'])
    with sqlite3.connect(settings.cloud_db_path) as db:
        db.execute("UPDATE recoveries SET expires_at='2000-01-01T00:00:00Z'")
    assert write(client, '/api/identity/recover', {'recovery': recovery, 'password': 'New-password-12345'}).status_code == 400
    assert write(client, '/api/identity/login', {'username': 'alice', 'password': 'Password-alice-123'}).status_code == 200


def test_invite_consumption_is_atomic_across_connections(identity):
    from concurrent.futures import ThreadPoolExecutor
    _, service, admin, _ = identity
    invite = service.create_invite(admin)
    def attempt(username):
        try:
            return service.register(username, 'Password-user-123', invite, username).principal
        except IdentityError:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ['alice', 'bob']))
    assert sum(result is not None for result in results) == 1


def test_csrf_issuance_is_rate_limited_without_cookie(identity):
    _, _, _, client = identity
    for _ in range(60):
        client.cookies.clear()
        assert client.get('/api/identity/csrf').status_code == 200
    client.cookies.clear()
    assert client.get('/api/identity/csrf').status_code == 429


def test_v2_upgrade_is_atomic_idempotent_and_preserves_users(tmp_path):
    from game_assistant.migrations.cloud_v1 import migrate_cloud_schema
    from game_assistant.migrations.cloud_v2 import migrate_identity_schema
    with sqlite3.connect(tmp_path / 'migration.db') as db:
        migrate_cloud_schema(db)
        db.execute("INSERT INTO users(user_id,username,password_hash) VALUES('owner','owner','hash')")
        db.execute('CREATE TABLE recoveries(conflict TEXT)')
        db.commit()
        with pytest.raises(sqlite3.OperationalError):
            migrate_identity_schema(db)
        assert db.execute('PRAGMA user_version').fetchone()[0] == 1
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='preauth_sessions'").fetchone()
        db.execute('DROP TABLE recoveries')
        db.commit()
        assert migrate_identity_schema(db) == 2
        assert migrate_identity_schema(db) == 2
        assert db.execute('SELECT user_id FROM users').fetchone()[0] == 'owner'


def test_current_session_revoke_invalidates_access(identity):
    register(identity)
    client = identity[3]
    session_id = client.get('/api/identity/sessions').json()['sessions'][0]['session_id']
    assert write(client, '/api/identity/sessions/' + session_id, method='delete').status_code == 200
    assert client.get('/api/identity/me').status_code == 401


def test_csrf_is_stable_for_two_tabs_in_one_session(identity):
    register(identity)
    client = identity[3]
    first_tab = client.get('/api/identity/csrf').json()['csrf_token']
    second_tab = client.get('/api/identity/csrf').json()['csrf_token']
    assert first_tab == second_tab
    assert first_tab != client.cookies.get('__Host-ga_session')
    assert client.post('/api/identity/logout', headers={'X-CSRF-Token': first_tab}).status_code == 200


def test_new_recovery_invalidates_old_and_used_codes(identity):
    data = register(identity)
    _, service, admin, client = identity
    old = service.create_recovery(admin, data['user_id'])
    latest = service.create_recovery(admin, data['user_id'])
    for code in [old]:
        assert write(client, '/api/identity/recover', {'recovery': code, 'password': 'New-password-12345'}).status_code == 400
    assert write(client, '/api/identity/recover', {'recovery': latest, 'password': 'New-password-12345'}).status_code == 200
    for code in [old, latest]:
        assert write(client, '/api/identity/recover', {'recovery': code, 'password': 'Another-password-12345'}).status_code == 400


def test_local_cli_bootstrap_invite_recovery(tmp_path, monkeypatch, capsys):
    from game_assistant.identity import cli
    config = tmp_path / 'config.toml'
    db_path = (tmp_path / 'cloud.db').as_posix()
    config.write_text(f'cloud_db_path = "{db_path}"\n', encoding='utf-8')
    monkeypatch.setattr('builtins.input', lambda prompt: 'operator')
    monkeypatch.setattr(cli, 'getpass', lambda prompt: 'Operator-password-123')
    assert cli.main(['--config', str(config), 'bootstrap-admin']) == 0
    output = capsys.readouterr().out
    assert 'Operator-password-123' not in output
    with sqlite3.connect(db_path) as db:
        user_id = db.execute('SELECT user_id FROM users').fetchone()[0]
    assert cli.main(['--config', str(config), 'invite']) == 0
    assert 'Invite code:' in capsys.readouterr().out
    assert cli.main(['--config', str(config), 'recovery', user_id]) == 0
    assert 'Recovery code:' in capsys.readouterr().out
    with sqlite3.connect(db_path) as db:
        assert db.execute('SELECT COUNT(*) FROM sessions WHERE revoked_at IS NULL').fetchone()[0] == 0

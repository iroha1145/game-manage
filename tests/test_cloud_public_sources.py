"""Source selection regressions with synthetic data and real snapshot storage."""
import json
from datetime import datetime, timedelta, timezone


from game_assistant.accounts.query import CloudPublicQuery
from game_assistant.models import FetchResult
from game_assistant.snapshots import SnapshotStore
from tests.test_api import FakeRegistry
from tests.test_registry import DummyAdapter


class Bili:
    def __init__(self, game, rows=(), **state):
        self.sources = {game: '123'}
        self.store = self
        self.rows = list(rows)
        self.data = state

    def state(self, game, uid):
        return self.data

    def news(self, game):
        return self.rows

    def calendar(self, game):
        return {'events': self.rows, 'version': '3.6'}


def query(game='wuthering_waves', rows=(), **state):
    class Adapter(DummyAdapter):
        game_id = game
    store = SnapshotStore(':memory:')
    return CloudPublicQuery(FakeRegistry(Adapter()), store, bilibili=Bili(game, rows, **state)), store


def save(store, game, cap, rows, time):
    store.save(game, cap, json.dumps(rows))
    store._conn.execute('UPDATE snapshots SET fetched_at=? WHERE game_id=? AND capability=?', (time, game, cap))
    store._conn.commit()


def test_empty_successful_bili_does_not_mask_failed_retained_calendar():
    now = datetime.now(timezone.utc).isoformat()
    q, store = query(status='ok', last_success=now, history_complete=True)
    old = '2026-01-01T00:00:00+00:00'
    save(store, 'wuthering_waves', 'events', [{'name': '旧活动'}], old)
    store.record_poll('wuthering_waves', 'events', FetchResult(ok=False, error='原生失败', error_kind='source_error'))
    result = q.read('wuthering_waves', 'events')
    assert result.state == 'error' and result.fetched_at == old
    assert result.complete is None
    assert result.primary_source == 'community' and result.stale
    assert result.poll_status['source_statuses']['community']['error'] == '原生失败'


def test_bili_success_does_not_refresh_old_official_endfield_calendar():
    now = datetime.now(timezone.utc).isoformat()
    q, store = query('endfield', status='ok', last_success=now, history_complete=True)
    old = '2026-01-01T00:00:00+00:00'
    save(store, 'endfield', 'events', [{'name': '官网活动', 'version': '1.0'}], old)
    store.record_poll('endfield', 'events', FetchResult(ok=False, error_kind='source_error'))
    result = q.read('endfield', 'events')
    assert result.fetched_at == old and result.state == 'error'
    assert result.primary_source == 'official' and result.version == '1.0'
    assert result.stale and result.payload[0]['source_stale']


def test_expired_successful_native_snapshot_is_stale_without_changing_poll_state():
    q, store = query()
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    save(store, 'wuthering_waves', 'events', [{'name': '旧活动'}], old)
    store.record_poll('wuthering_waves', 'events', FetchResult(ok=True), now=datetime.fromisoformat(old))
    result = q.read('wuthering_waves', 'events')
    assert result.state == 'ok' and result.stale
    assert result.payload[0]['source_stale']


def test_bili_history_completeness_is_not_calendar_coverage():
    now = datetime.now(timezone.utc).isoformat()
    q, _ = query(rows=[{'name': 'B站活动', 'source': 'bilibili'}], status='ok', last_success=now, history_complete=True)
    result = q.read('wuthering_waves', 'events')
    assert result.complete is None and result.primary_source == 'bilibili'
    assert result.version == '3.6' and result.fetched_at == now
    assert result.poll_status['source_statuses']['bilibili']['state'] == 'ok'


def test_failed_bili_preserves_native_rows_and_reports_degradation():
    q, store = query(status='error', message='B站不可达', failures=1)
    now = datetime.now(timezone.utc).isoformat()
    save(store, 'wuthering_waves', 'events', [{'name': '社区活动'}], now)
    store.record_poll('wuthering_waves', 'events', FetchResult(ok=True))
    result = q.read('wuthering_waves', 'events')
    assert result.state == 'error' and not result.stale
    assert result.payload[0]['name'] == '社区活动'
    assert result.poll_status['source_statuses']['bilibili']['error'] == 'B站不可达'


def test_public_qq_partial_failure_labels_fresh_native_content_as_available():
    from game_assistant.qq.commands import render_result
    from game_assistant.accounts.models import QueryResult
    q, store = query(status='error', message='B站不可达', failures=1)
    now = datetime.now(timezone.utc).isoformat()
    save(store, 'wuthering_waves', 'events', [{'name': '最新社区活动'}], now)
    store.record_poll('wuthering_waves', 'events', FetchResult(ok=True))
    result = q.read('wuthering_waves', 'events')
    text = render_result('鸣潮活动', result, 'events')
    assert '部分来源不可用，显示可用来源数据' in text and '旧快照' not in text
    # Private failures and genuinely stale public content keep the old-cache warning.
    private = QueryResult([{'name': '旧记录'}], now, 'error', None)
    assert '显示旧快照' in render_result('私人查询', private, 'events')
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    save(store, 'wuthering_waves', 'events', [{'name': '旧社区活动'}], old)
    assert '显示旧快照' in render_result('鸣潮活动', q.read('wuthering_waves', 'events'), 'events')


def test_partial_and_expired_bili_keep_rows_warn_and_use_contributing_time():
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    q, _ = query(rows=[{'name': 'B站旧活动', 'source': 'bilibili', 'source_stale': True}],
                 status='ok', last_success=old)
    result = q.read('wuthering_waves', 'events')
    assert result.state == 'error' and result.stale and len(result.payload) == 1
    assert result.poll_status['error_kind'] == 'partial_data'
    assert result.fetched_at == old


def test_announcement_failure_and_time_are_separate_from_news():
    q, store = query()
    old = '2026-01-01T00:00:00+00:00'
    save(store, 'wuthering_waves', 'announcement', [{'title': '公告'}], old)
    store.record_poll('wuthering_waves', 'announcement', FetchResult(ok=False, error='正文失败', error_kind='source_error'))
    result = q.read('wuthering_waves', 'news')
    assert result.state == 'error' and result.fetched_at == old and result.stale
    assert result.poll_status['source_statuses']['announcement']['error'] == '正文失败'


def test_deduplicated_native_calendar_does_not_refresh_bili_content():
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    event = {'name': '同一活动', 'source': 'bilibili', 'end_at': '2026-11-01T05:59:00+08:00'}
    q, store = query(rows=[event], status='ok', last_success=old)
    save(store, 'wuthering_waves', 'events', [{**event, 'source': 'community', 'version': '3.6'}], datetime.now(timezone.utc).isoformat())
    result = q.read('wuthering_waves', 'events')
    assert len(result.payload) == 1 and result.fetched_at == old and result.stale


def test_native_article_body_repair_counts_as_actual_contribution():
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    q, store = query(rows=[{'title': '同一公告', 'source': 'bilibili', 'body': ''}], status='ok', last_success=old)
    save(store, 'wuthering_waves', 'announcement', [{'title': '同一公告', 'body': '社区完整正文', 'content_status': 'full'}], now)
    result = q.read('wuthering_waves', 'news')
    assert len(result.payload) == 1 and result.fetched_at == now
    assert result.payload[0]['body'] == '社区完整正文'


def test_same_version_community_event_survives_bili_merge_without_version_in_title():
    now = datetime.now(timezone.utc).isoformat()
    q, store = query(rows=[{'name': 'B站活动', 'source': 'bilibili'}], status='ok', last_success=now)
    save(store, 'wuthering_waves', 'events', [{'name': '独立卡池', 'version': '3.6', 'source_title': '独立唤取公告'}], now)
    result = q.read('wuthering_waves', 'events')
    assert {r['name'] for r in result.payload} == {'B站活动', '独立卡池'}


def test_public_qq_reply_warns_when_successful_cache_has_expired():
    from game_assistant.qq.commands import render_result
    q, store = query()
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    save(store, 'wuthering_waves', 'events', [{'name': '旧活动'}], old)
    store.record_poll('wuthering_waves', 'events', FetchResult(ok=True), now=datetime.fromisoformat(old))
    text = render_result('鸣潮活动', q.read('wuthering_waves', 'events'), 'events')
    assert '旧活动' in text and '过期' in text and '完整性：未知' in text


def test_cloud_http_preserves_public_source_metadata(tmp_path):
    from fastapi.testclient import TestClient
    from game_assistant.cloud_app import create_cloud_app
    from tests.test_account_queries import cloud_settings
    from tests.test_identity import write
    app = create_cloud_app(cloud_settings(tmp_path), start_scheduler=False)
    admin = app.state.identity.bootstrap_admin('admin', 'Admin-password-123')
    invite = app.state.identity.create_invite(admin)
    with TestClient(app, base_url='https://cloud.example') as client:
        assert client.get('/api/public/games/wuthering_waves/events').status_code == 401
        assert write(client, '/api/identity/register', {'username': 'alice',
            'password': 'Password-alice-123', 'invite': invite}).status_code == 200
        def seed():
            old = '2026-01-01T00:00:00+00:00'
            save(app.state.store, 'wuthering_waves', 'events', [{'name': '旧活动', 'version': '3.6'}], old)
            app.state.store.record_poll('wuthering_waves', 'events', FetchResult(ok=True), now=datetime.fromisoformat(old))
        client.portal.call(seed)
        response = client.get('/api/public/games/wuthering_waves/events')
        assert response.status_code == 200
        data = response.json()
        assert data['state'] == 'ok' and data['stale'] is True
        assert data['primary_source'] == 'community' and data['version'] == '3.6'
        assert data['poll_status']['source_statuses']['community']['state'] == 'ok'
        assert data['complete'] is None

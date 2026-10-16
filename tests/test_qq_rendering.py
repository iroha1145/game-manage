import asyncio
from io import BytesIO
import threading

from PIL import Image
import pytest

from game_assistant.accounts.models import AccountScope, QueryResult
from game_assistant.qq.commands import render_result
from tests.qq_test_fonts import cjk_font_path as cjk_font


def renderer_module():
    from game_assistant.qq import rendering
    return rendering


def result(text='昵称：测试\n等级：0', timestamp='2026-10-12T12:00:00Z'):
    return QueryResult({'text': text}, timestamp, 'ok', None)


def test_cache_includes_account_and_snapshot():
    module = renderer_module()
    cache = module.SummaryRenderer(font_path=cjk_font())
    scope = AccountScope('user', 'account', 'role')
    keys = {cache.cache_key(s, r) for s, r in (
        (scope, result()), (AccountScope('other', 'account', 'role'), result()),
        (AccountScope('user', 'other', 'role'), result()),
        (AccountScope('user', 'account', 'other'), result()),
        (scope, result(timestamp='2026-10-12T12:01:00Z')), (scope, result('等级：1')))}
    assert len(keys) == 6
    png = cache.render_summary(scope, result())
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    assert Image.open(BytesIO(png)).width <= 1080
    assert len(png) <= cache.max_bytes
    cache.render_summary(AccountScope('other', 'account', 'role'), result('其他用户'))
    assert len(cache.cache) == 2
    cache.invalidate_account('user', 'account')
    assert len(cache.cache) == 1
    assert cache.cache_key(scope, QueryResult({'text': '摘要', 'grant_version': 1}, None, 'ok', None)) != cache.cache_key(scope, QueryResult({'text': '摘要', 'grant_version': 2}, None, 'ok', None))


def test_missing_fields_render_unknown():
    module = renderer_module()
    original = QueryResult({'nickname': None, 'level': 0}, None, 'ok', None)
    text = render_result('异环', original, 'account')
    assert '昵称：未知' in text and '等级：0' in text and '完整性：未知' in text
    cache = module.SummaryRenderer(font_path=cjk_font())
    png = cache.render_summary(AccountScope('user', 'account', 'role'), result(text))
    assert Image.open(BytesIO(png)).height > 100


def test_no_cjk_font_or_arbitrary_payload_returns_safe_failure(tmp_path):
    module = renderer_module()
    cache = module.SummaryRenderer(font_path=str(tmp_path / 'missing.ttf'))
    with pytest.raises(module.RenderingUnavailable):
        cache.render_summary(AccountScope('user', 'account', 'role'), result())
    cache = module.SummaryRenderer(font_path=cjk_font())
    with pytest.raises(module.RenderingUnavailable):
        cache.render_summary(AccountScope('user', 'account', 'role'), QueryResult({'token': 'secret'}, None, 'ok', None))


async def test_render_queue_does_not_exceed_reply_window():
    module = renderer_module()
    started, finish = threading.Event(), threading.Event()
    scope = AccountScope('user', 'account', 'role')
    class SlowRenderer:
        def render_summary(self, scope, query):
            started.set()
            finish.wait(2)
            return b'png'
    queue = module.RenderQueue(SlowRenderer(), queue_limit=1)
    first = asyncio.create_task(queue.render(scope, result(), budget_seconds=0.1))
    await asyncio.to_thread(started.wait, 1)
    try:
        assert await queue.render(scope, result(), budget_seconds=0.01) is None
        assert await first is None
        # Timed-out work still occupies the only rendering slot until it really ends.
        assert await queue.render(scope, result(), budget_seconds=0.1) is None
    finally:
        finish.set()
        await queue.aclose()
    assert await queue.render(scope, result(), budget_seconds=0) is None


async def test_multi_user_rendering_isolated_and_cache_bounded():
    module = renderer_module()
    renderer = module.SummaryRenderer(font_path=cjk_font(), cache_entries=2)
    queue = module.RenderQueue(renderer)
    values = await asyncio.gather(*(queue.render(AccountScope(str(n), str(n), str(n)), result(f'账号：{n}'), budget_seconds=3) for n in range(3)))
    assert all(values) and len(set(values)) == 3
    assert len(renderer.cache) == 2
    await queue.aclose()


def test_named_role_filters_only_owned_cached_list():
    from types import SimpleNamespace
    from game_assistant.qq.query_routes import QqQueryService, QueryBody
    from game_assistant.qq.models import QqIdentity
    from game_assistant.identity.models import Principal
    scope = AccountScope('u', 'a', 'r')
    reads = []
    class Query:
        accounts = SimpleNamespace(require_scope=lambda p, a, r: scope)
        def list_accounts(self, p):
            return [dict(game='wuthering_waves', provider='kuro', account_id='a', state='active', is_default=True, roles=[dict(role_id='r', is_default=True)])]
        def capabilities(self, scope):
            return ['roles']
        def read(self, scope, capability):
            reads.append((scope, capability))
            return QueryResult([{'name': '今汐', 'level': 80}, {'name': '长离', 'level': None}], None, 'ok', None)
    service = QqQueryService(SimpleNamespace(resolve_qq_identity=lambda i: Principal('u', False)), Query(), None)
    identity = QqIdentity('app', 'group', 'g', 's')
    response = service.query(identity, 'roles', 'wuthering_waves', role_name='长离')
    assert '长离' in response['text'] and '今汐' not in response['text'] and '未知' in response['text']
    assert '未找到' in service.query(identity, 'roles', 'wuthering_waves', role_name='他人')['text']
    assert all(s == scope and capability == 'roles' for s, capability in reads)
    with pytest.raises(ValueError):
        QueryBody(identity={'app_id':'app','scene':'group','group_openid':'g','sender_openid':'s'}, command='summary', game='nte', role_name='他人')


async def test_upload_failure_falls_back_to_text(tmp_path):
    from datetime import datetime, timezone, timedelta
    from game_assistant.qq.client import QqReply
    from game_assistant.qq.transport import BotDispatcher, BotState
    from game_assistant.qq.models import InboundMessage, QqIdentity
    now = datetime.now(timezone.utc)
    message = InboundMessage(QqIdentity('app', 'group', 'group', 'sender'), 'msg', '/yh', now.isoformat(), (now + timedelta(minutes=5)).isoformat())
    calls = []
    class Service:
        async def execute(self, message):
            return QqReply('文字摘要', b'png')
    class Sender:
        async def send_image(self, message, image, sequence):
            calls.append(('upload', sequence))
            raise renderer_module().ImagePreparationFailed('qq_upload_failed')
        async def send_text(self, message, text, sequence):
            calls.append((text, sequence))
            return 'id'
    state = BotState(tmp_path / 'bot.db')
    dispatcher = BotDispatcher(Service(), Sender(), state)
    await dispatcher.handle_message(message)
    await dispatcher.handle_message(message)
    assert calls == [('upload', 1), ('文字摘要\n图片暂不可用，当前为文字摘要；完整内容请到网站查看。', 1)]
    assert state.connection.execute('SELECT state FROM replies').fetchone()[0] == 'sent'
    state.close()


async def test_ambiguous_image_send_never_falls_back_or_repeats(tmp_path):
    from datetime import datetime, timezone, timedelta
    from game_assistant.qq.client import QqReply
    from game_assistant.qq.transport import BotDispatcher, BotState
    from game_assistant.qq.models import InboundMessage, QqIdentity
    now = datetime.now(timezone.utc)
    message = InboundMessage(QqIdentity('app', 'group', 'group', 'sender'), 'msg', '/yh', now.isoformat(), (now + timedelta(minutes=5)).isoformat())
    calls = []
    class Service:
        async def execute(self, message):
            return QqReply('文字摘要', b'png')
    class Sender:
        async def send_image(self, message, image, sequence):
            calls.append('image')
            raise TimeoutError('uncertain')
        async def send_text(self, *args):
            calls.append('text')
    state = BotState(tmp_path / 'bot.db')
    dispatcher = BotDispatcher(Service(), Sender(), state)
    await dispatcher.handle_message(message)
    await dispatcher.handle_message(message)
    assert calls == ['image']
    assert state.connection.execute('SELECT state FROM replies').fetchone()[0] == 'uncertain'
    state.close()


async def test_official_image_upload_does_not_send_message_and_obeys_deadline():
    import base64
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    from game_assistant.qq.client import OfficialQqClient
    from game_assistant.qq.models import InboundMessage, QqIdentity
    now = datetime.now(timezone.utc)
    message = InboundMessage(QqIdentity('app', 'group', 'group', 'sender'), 'msg', '/yh', now.isoformat(), (now + timedelta(minutes=5)).isoformat())
    calls = []
    class API:
        def __init__(self, *a, **kw):
            pass
        def setup(self, http):
            pass
        async def request(self, method, path, body, **kwargs):
            calls.append((path, body))
            return {'file_info': 'opaque', 'ttl': 60} if path.endswith('/files') else {'id': 'image-id'}
    client = OfficialQqClient('app', 'fixture-secret', None, None, sdk=SimpleNamespace(QQApiClient=API))
    png = renderer_module().SummaryRenderer(font_path=cjk_font()).render_summary(AccountScope('u', 'a', 'r'), result())
    assert await client.send_image(message, png, 1) == 'image-id'
    assert calls[0] == ('/v2/groups/group/files', {'file_type': 1, 'file_data': base64.b64encode(png).decode('ascii'), 'srv_send_msg': False})
    assert calls[1] == ('/v2/groups/group/messages', {'msg_type': 7, 'media': {'file_info': 'opaque'}, 'msg_id': 'msg', 'msg_seq': 1})
    client.now = lambda: now + timedelta(minutes=6)
    with pytest.raises(renderer_module().ImagePreparationFailed):
        await client.send_image(message, png, 1)
    assert len(calls) == 2
    await client.aclose()


async def test_sdk_upload_error_is_known_before_any_message_send(caplog):
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    from game_assistant.qq.client import OfficialQqClient
    from game_assistant.qq.models import InboundMessage, QqIdentity
    now = datetime.now(timezone.utc)
    message = InboundMessage(QqIdentity('app', 'group', 'g', 's'), 'id', '/yh', now.isoformat(), (now + timedelta(minutes=5)).isoformat())
    calls = []
    class API:
        def __init__(self, *a, **kw):
            pass
        def setup(self, http):
            pass
        async def request(self, method, path, body):
            calls.append(path)
            raise TimeoutError('private-sdk-detail')
    client = OfficialQqClient('app', 'fixture', None, None, sdk=SimpleNamespace(QQApiClient=API))
    image = BytesIO()
    Image.new('RGB',(32,32),'#14171c').save(image,'PNG')
    with pytest.raises(renderer_module().ImagePreparationFailed) as error:
        await client.send_image(message, image.getvalue(), 1)
    assert calls == ['/v2/groups/g/files']
    assert 'private-sdk-detail' not in str(error.value) and 'private-sdk-detail' not in caplog.text
    await client.aclose()


@pytest.mark.parametrize('change', ['revoke', 'unlink', 'rotate'])
async def test_central_render_rechecks_revoke_and_unlink_after_await(tmp_path, change):
    from types import SimpleNamespace
    from tests.test_account_queries import query_fixture
    from game_assistant.qq.query_routes import QqQueryService
    from game_assistant.qq.models import QqIdentity
    from game_assistant.identity.models import Principal
    from game_assistant.qq.bindings import QqBindingError
    accounts, scope, store, query = await query_fixture(tmp_path)
    store.save_scoped(scope, 'account', '{"nickname":"PRIVATE","level":0}', 1)
    linked = [True]
    def resolve(identity):
        if not linked[0]:
            raise QqBindingError('qq_link_required', 403)
        return Principal('a', False)
    class Queue:
        renderer = renderer_module().SummaryRenderer(font_path=cjk_font())
        async def render(self, scope, result, **kwargs):
            if change == 'revoke':
                accounts.revoke(Principal('a', False), scope.account_id)
            elif change == 'unlink':
                linked[0] = False
            else:
                accounts.connection.execute('UPDATE grants SET version=version+1')
            return b'png'
    service = QqQueryService(SimpleNamespace(resolve_qq_identity=resolve), query, None, render_queue=Queue())
    response = await service.query_reply(QqIdentity('app', 'group', 'group', 'sender'), 'summary', 'nte', image_requested=True, budget_seconds=5)
    assert 'image' not in response and 'PRIVATE' not in response['text']


async def test_central_png_envelope_contains_only_safe_summary(tmp_path):
    import base64
    from types import SimpleNamespace
    from tests.test_account_queries import query_fixture
    from game_assistant.qq.query_routes import QqQueryService
    from game_assistant.qq.models import QqIdentity
    from game_assistant.identity.models import Principal
    accounts, scope, store, query = await query_fixture(tmp_path)
    store.save_scoped(scope, 'account', '{"nickname":"玩家","level":0,"token":"private-token","uid":"123456789"}', 1)
    module = renderer_module()
    service = QqQueryService(SimpleNamespace(resolve_qq_identity=lambda i: Principal('a', False)), query, None,
                             render_queue=module.RenderQueue(module.SummaryRenderer(font_path=cjk_font())))
    identity = QqIdentity('app', 'group', 'g', 's')
    text_only = await service.query_reply(identity, 'summary', 'nte')
    assert set(text_only) == {'text'}
    response = await service.query_reply(identity, 'summary', 'nte', image_requested=True, budget_seconds=3)
    assert set(response) == {'text', 'image'}
    assert 'private-token' not in response['text'] and '123456789' not in response['text']
    assert Image.open(BytesIO(base64.b64decode(response['image']))).width <= 1080
    accounts.revoke(Principal('a', False), scope.account_id)
    assert not service.render_queue.renderer.cache
    await service.aclose()


async def test_internal_image_opt_in_and_invalid_image_falls_back():
    import json
    from datetime import datetime, timedelta, timezone
    import httpx
    from game_assistant.qq.client import InternalQqClient
    from game_assistant.qq.models import InboundMessage, QqIdentity
    requests = []
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={'text':'等级：未知', 'image':'invalid base64'})
    http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    now = datetime.now(timezone.utc)
    msg = InboundMessage(QqIdentity('app', 'group', 'g', 's'), 'id', '/yh', now.isoformat(), (now + timedelta(minutes=5)).isoformat())
    service = InternalQqClient('http://127.0.0.1:8020', 'fixture', http=http)
    assert await service.execute(msg) == '等级：未知'
    assert 'image_requested' not in requests[-1]
    service.images_enabled = True
    assert await service.execute(msg) == '等级：未知'
    assert requests[-1]['image_requested'] is True and 0 < requests[-1]['render_budget_seconds'] <= 10
    await http.aclose()


def test_actual_encoded_bytes_are_capped():
    module = renderer_module()
    renderer = module.SummaryRenderer(font_path=cjk_font(), max_bytes=100)
    with pytest.raises(module.RenderingUnavailable, match='size_limit'):
        renderer.render_summary(AccountScope('u', 'a', 'r'), result())


async def test_invalidation_during_cpu_render_does_not_reinsert_cache():
    import time
    module = renderer_module()
    renderer = module.SummaryRenderer(font_path=cjk_font())
    started, finish = threading.Event(), threading.Event()
    original_font = renderer._font
    def delayed_font():
        started.set()
        finish.wait(1)
        return original_font()
    renderer._font = delayed_font
    queue = module.RenderQueue(renderer)
    task = asyncio.create_task(queue.render(AccountScope('u', 'a', 'r'), result(), budget_seconds=2))
    await asyncio.to_thread(started.wait, 1)
    try:
        start = time.monotonic()
        renderer.invalidate_account('u', 'a')
        assert time.monotonic() - start < 0.1
    finally:
        finish.set()
    await task
    assert len(renderer.cache) == 0
    await queue.aclose()


def test_cloud_shutdown_drains_pending_render_and_removes_listener(tmp_path):
    import time
    from fastapi.testclient import TestClient
    from tests.test_account_queries import cloud_settings
    from game_assistant.cloud_app import create_cloud_app
    settings = cloud_settings(tmp_path, qq_app_id='app', qq_service_token='fixture', qq_images_enabled=True, qq_image_font_path=cjk_font())
    app = create_cloud_app(settings, start_scheduler=False)
    with TestClient(app, base_url='https://cloud.example') as client:
        service = app.state.qq_query
        queue = service.render_queue
        # CI runs the backend tests before building the frontend; the render must not depend on that build.
        (tmp_path / 'dist').mkdir()
        (tmp_path / 'dist/render.html').write_text('<!doctype html>')
        queue.renderer.dist = tmp_path / 'dist'
        original_font = queue.renderer._font
        def slow_font():
            time.sleep(0.25)
            return original_font()
        queue.renderer._font = slow_font
        async def render_late():
            return await queue.render(AccountScope('fixture', 'fixture', 'fixture'), result(), budget_seconds=0.01)
        assert client.portal.call(render_late) is None
        assert queue.pending == 1
        listeners = service.query_service.accounts._listeners
    assert queue.pending == 0
    assert service.invalidate not in listeners

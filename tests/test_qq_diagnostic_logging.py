"""Fallback diagnostics expose fixed categories, never request or exception data."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytest
import httpx

from game_assistant.accounts.models import AccountScope, QueryResult
from game_assistant.qq.client import QqReply
from game_assistant.qq.models import InboundMessage, QqIdentity
from game_assistant.qq.rendering import ImagePreparationFailed, RenderQueue, RenderingUnavailable
from game_assistant.qq.transport import BotDispatcher, BotState


PRIVATE = 'private-token-user-message-snapshot-openid'
SCOPE = AccountScope(PRIVATE, PRIVATE, PRIVATE)
RESULT = QueryResult({'text': PRIVATE}, PRIVATE, 'ok', None)


def assert_safe_log(caplog, logger, expected):
    records = [record for record in caplog.records if record.name == logger]
    assert any(record.getMessage() == expected for record in records)
    assert PRIVATE not in caplog.text
    assert all(record.exc_info is None and record.stack_info is None for record in records)
    assert all(PRIVATE not in repr(record.__dict__) for record in records)


@pytest.mark.parametrize(('error', 'code'), [
    (RenderingUnavailable('qq_browser_not_ready'), 'qq_browser_not_ready'),
    (RenderingUnavailable('qq_browser_runtime_unavailable'), 'qq_browser_runtime_unavailable'),
    (RenderingUnavailable('qq_browser_cleanup_unconfirmed'), 'qq_browser_cleanup_unconfirmed'),
    (RenderingUnavailable('qq_image_pixel_limit'), 'qq_image_pixel_limit'),
    (RenderingUnavailable('qq_image_size_limit'), 'qq_image_size_limit'),
    (RenderingUnavailable(PRIVATE), 'qq_render_unavailable'),
    (RuntimeError(PRIVATE), 'qq_render_exception'),
    (TimeoutError(PRIVATE), 'qq_render_timeout'),
])
async def test_render_failure_logs_only_predefined_category(caplog, error, code):
    class Renderer:
        async def render_summary_async(self, *args, **kwargs):
            raise error

    caplog.set_level(logging.WARNING)
    queue = RenderQueue(Renderer())
    try:
        outcome = await queue.render(SCOPE, RESULT, budget_seconds=1)
        assert outcome is error if code in ('qq_image_pixel_limit', 'qq_image_size_limit') else outcome is None
    finally:
        await queue.aclose()
    assert_safe_log(caplog, 'game_assistant.qq.rendering', 'QQ render fallback: ' + code)


async def test_queue_budget_capacity_and_deadline_are_distinguishable(caplog):
    entered, finish = asyncio.Event(), asyncio.Event()
    calls = []

    class Renderer:
        async def render_summary_async(self, *args, **kwargs):
            calls.append(1)
            entered.set()
            await finish.wait()
            return b'image'

    caplog.set_level(logging.WARNING)
    queue = RenderQueue(Renderer(), queue_limit=1)
    assert await queue.render(SCOPE, RESULT, budget_seconds=0) is None
    first = asyncio.create_task(queue.render(SCOPE, RESULT, budget_seconds=.05))
    await entered.wait()
    try:
        assert await queue.render(SCOPE, RESULT, budget_seconds=1) is None
        assert await first is None
        assert queue.pending == 1  # Timeout must not release the real worker.
        assert await queue.render(SCOPE, RESULT, budget_seconds=1) is None
    finally:
        finish.set()
        await queue.aclose()
    assert calls == [1]
    for code in ('qq_render_budget_exhausted', 'qq_render_queue_full', 'qq_render_deadline'):
        assert_safe_log(caplog, 'game_assistant.qq.rendering', 'QQ render fallback: ' + code)


async def test_work_expired_while_queued_logs_safe_category(caplog, monkeypatch):
    from game_assistant.qq import rendering

    class Renderer:
        async def render_summary_async(self, *args, **kwargs):
            pytest.fail('Expired queued work must not start the renderer')

    # Patch the module's clock object, without altering asyncio's real clock.
    from types import SimpleNamespace
    ticks = iter([100, 100, 102])
    monkeypatch.setattr(rendering, 'time', SimpleNamespace(monotonic=lambda: next(ticks)))
    queue = RenderQueue(Renderer())
    try:
        assert await queue.render(SCOPE, RESULT, budget_seconds=1) is None
    finally:
        await queue.aclose()
    assert_safe_log(caplog, 'game_assistant.qq.rendering', 'QQ render fallback: qq_render_queue_expired')


@pytest.mark.parametrize(('error_code', 'logged_code'), [
    ('qq_image_invalid', 'qq_image_invalid'),
    ('qq_image_deadline', 'qq_image_deadline'),
    ('qq_image_upload_failed', 'qq_image_upload_failed'),
    ('qq_image_upload_timeout', 'qq_image_upload_timeout'),
    (PRIVATE, 'qq_image_preparation_failed'),
    ('qq_image_upload_failed\n' + PRIVATE, 'qq_image_preparation_failed'),
])
async def test_upload_fallback_logs_safe_category_and_does_not_repeat(tmp_path, caplog, error_code, logged_code):
    now = datetime.now(timezone.utc)
    message = InboundMessage(QqIdentity(PRIVATE, 'group', PRIVATE, PRIVATE), PRIVATE,
                             PRIVATE, now.isoformat(), (now + timedelta(minutes=5)).isoformat())
    calls = []

    class Service:
        async def execute(self, message):
            return QqReply(PRIVATE, b'image')

    class Sender:
        async def send_image(self, message, image, sequence):
            calls.append(('image', sequence))
            raise ImagePreparationFailed(error_code)

        async def send_text(self, message, text, sequence):
            calls.append(('text', sequence))
            assert PRIVATE in text
            return PRIVATE

    state = BotState(tmp_path / 'bot.db')
    try:
        dispatcher = BotDispatcher(Service(), Sender(), state)
        await dispatcher.handle_message(message)
        await dispatcher.handle_message(message)
        assert calls == [('image', 1), ('text', 1)]
        assert state.connection.execute('SELECT state FROM replies').fetchone()[0] == 'sent'
    finally:
        state.close()
    assert_safe_log(caplog, 'game_assistant.qq.transport', 'QQ image preparation fallback: ' + logged_code)


@pytest.mark.parametrize(('error', 'expected'), [
    (TimeoutError(PRIVATE), 'qq_image_upload_timeout'),
    (RuntimeError(PRIVATE), 'qq_image_upload_failed'),
])
async def test_official_upload_failure_retains_only_safe_category(caplog, error, expected):
    from io import BytesIO
    from types import SimpleNamespace
    from PIL import Image
    from game_assistant.qq.client import OfficialQqClient

    calls = []

    class API:
        def __init__(self, *args, **kwargs):
            pass

        def setup(self, http):
            pass

        async def request(self, method, path, body, *, timeout=None):
            calls.append(body['srv_send_msg'])
            raise error

    now = datetime.now(timezone.utc)
    message = InboundMessage(QqIdentity(PRIVATE, 'group', PRIVATE, PRIVATE), PRIVATE,
                             PRIVATE, now.isoformat(), (now + timedelta(minutes=5)).isoformat())
    image = BytesIO()
    Image.new('RGB', (32, 32)).save(image, 'PNG')
    client = OfficialQqClient(PRIVATE, PRIVATE, None, None, sdk=SimpleNamespace(QQApiClient=API))
    try:
        with pytest.raises(ImagePreparationFailed) as caught:
            await client.send_image(message, image.getvalue(), 1)
        assert str(caught.value) == expected
        assert calls == [False]  # No /messages request after upload failure.
        assert PRIVATE not in caplog.text
    finally:
        await client.aclose()


def mock_official_http(monkeypatch, handler):
    """Keep the real SDK and the production client's response-hook setup."""
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(handler)))


@pytest.mark.parametrize('code_field', ['code', 'err_code'])
@pytest.mark.parametrize(('api_code', 'expected'), [
    (40054010, '40054010'), (0, '0'), (True, 'unavailable'),
    ('40054010', 'unavailable'), (1.5, 'unavailable'),
    (-1, 'unavailable'), (2**31, 'unavailable'), (None, 'unavailable'),
])
async def test_real_sdk_upload_response_logs_only_http_status_and_numeric_code(monkeypatch, caplog, code_field, api_code, expected):
    from game_assistant.qq.client import OfficialQqClient

    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(400, json={code_field: api_code, 'message': PRIVATE, 'file_info': PRIVATE},
                              headers={'x-tps-trace-id': PRIVATE})

    mock_official_http(monkeypatch, handle)
    caplog.set_level(logging.INFO)
    client = OfficialQqClient(PRIVATE, PRIVATE, None, None)
    client.api._access_token, client.api._token_expires_at = PRIVATE, 9e12
    try:
        with pytest.raises(RuntimeError):
            await client.api.request('POST', '/v2/groups/' + PRIVATE + '/files', {'file_data': PRIVATE})
        assert len(requests) == 1
    finally:
        await client.aclose()
    assert_safe_log(caplog, 'game_assistant.qq.client',
                    'QQ image upload response: http_status=400 api_code=' + expected)


async def test_current_error_code_takes_precedence_over_legacy_code(monkeypatch, caplog):
    from game_assistant.qq.client import OfficialQqClient
    mock_official_http(monkeypatch, lambda request: httpx.Response(400, json={
        'err_code':40034005,'code':40054010,'message':PRIVATE,'trace_id':PRIVATE}))
    caplog.set_level(logging.INFO)
    client=OfficialQqClient(PRIVATE,PRIVATE,None,None)
    client.api._access_token,client.api._token_expires_at=PRIVATE,9e12
    try:
        with pytest.raises(RuntimeError):
            await client.api.request('POST','/v2/groups/target/files',{'file_data':PRIVATE})
    finally:await client.aclose()
    assert_safe_log(caplog,'game_assistant.qq.client',
                    'QQ image upload response: http_status=400 api_code=40034005')


async def test_upload_response_hook_preserves_sdk_body_and_ignores_other_routes(monkeypatch, caplog):
    import json
    from game_assistant.qq.client import OfficialQqClient

    body = {'file_info': PRIVATE, 'ttl': 3600, 'unknown': PRIVATE}
    reads = []
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            reads.append(1)
            yield json.dumps(body).encode()

    mock_official_http(monkeypatch, lambda request: httpx.Response(200, stream=Body()))
    caplog.set_level(logging.INFO)
    client = OfficialQqClient(PRIVATE, PRIVATE, None, None)
    client.api._access_token, client.api._token_expires_at = PRIVATE, 9e12
    try:
        assert await client.api.request('POST', '/v2/users/' + PRIVATE + '/files', {}) == body
        assert reads == [1]  # The hook and SDK share the one cached body read.
        assert_safe_log(caplog, 'game_assistant.qq.client',
                        'QQ image upload response: http_status=200 api_code=unavailable')
        caplog.clear()
        for url in ('https://example.invalid/v2/groups/target/files',
                    'https://api.bot.qq.com/v2/groups/target/messages',
                    'https://api.bot.qq.com/app/getAppAccessToken'):
            assert (await client.http.post(url, json={'private': PRIVATE})).json() == body
        assert not [record for record in caplog.records if record.name == 'game_assistant.qq.client']
    finally:
        await client.aclose()


@pytest.mark.parametrize('error_type', [httpx.ConnectTimeout, httpx.ReadTimeout])
async def test_real_sdk_wrapped_upload_timeout_keeps_safe_timeout_category(monkeypatch, caplog, error_type):
    from io import BytesIO
    from PIL import Image
    from game_assistant.qq.client import OfficialQqClient

    requests = []
    def handle(request):
        requests.append(request)
        raise error_type(PRIVATE, request=request)

    mock_official_http(monkeypatch, handle)
    client = OfficialQqClient(PRIVATE, PRIVATE, None, None)
    client.api._access_token, client.api._token_expires_at = PRIVATE, 9e12
    now = datetime.now(timezone.utc)
    message = InboundMessage(QqIdentity(PRIVATE, 'group', PRIVATE, PRIVATE), PRIVATE,
                             PRIVATE, now.isoformat(), (now + timedelta(minutes=5)).isoformat())
    image = BytesIO()
    Image.new('RGB', (32, 32)).save(image, 'PNG')
    try:
        with pytest.raises(ImagePreparationFailed) as caught:
            await client.send_image(message, image.getvalue(), 1)
        assert str(caught.value) == 'qq_image_upload_timeout'
        assert len(requests) == 1 and requests[0].url.path.endswith('/files')
        assert PRIVATE not in caplog.text
    finally:
        await client.aclose()

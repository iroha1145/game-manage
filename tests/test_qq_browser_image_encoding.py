"""Exercise the real renderer pipeline with deterministic browser screenshot bytes."""
import asyncio
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from game_assistant.accounts.models import AccountScope, QueryResult
from game_assistant.qq.browser_rendering import BrowserRenderer
from game_assistant.qq.render_snapshot import calendar_snapshot
from game_assistant.qq.rendering import RenderingUnavailable, RenderingPageUnavailable


def encoded_image(format, size_kib, *, quality=90, dimensions=(720, 100)):
    output = BytesIO()
    Image.new('RGB', dimensions, '#f5f5f5').save(output, format, **({'quality': quality} if format == 'JPEG' else {}))
    # Padding after the encoded image controls byte budgets without huge fixtures.
    return output.getvalue().ljust(size_kib * 1024, b'\0')


def renderer_boundary(monkeypatch, sizes, *, hard_kib=1024, height=100, delay_jpeg=False, pages=None, counts=(3, 3), dimensions=(720, 100)):
    renderer = BrowserRenderer(cache_entries=0, max_bytes=hard_kib * 1024)
    calls = []
    outputs = {key: encoded_image('PNG' if key == 'png' else 'JPEG', size,
                                 quality=key if isinstance(key, int) else 90, dimensions=dimensions)
               for key, size in sizes.items()}
    state = {}

    async def screenshot(**options):
        calls.append(options)
        if options['type'] == 'jpeg' and delay_jpeg == 'error':
            raise RuntimeError('optional browser encoding unavailable')
        if options['type'] == 'jpeg' and (delay_jpeg is True or delay_jpeg == options['quality']):
            await asyncio.Event().wait()
        return outputs[options.get('quality', 'png')]

    async def evaluate(expression, input=None):
        if input is not None:
            state.update(state='ready', job_id=input['job_id'], input_fingerprint=input['input_fingerprint'],
                         pages=pages if pages is not None else [{'width': 720, 'height': height}],
                         content_blocks=counts[0], displayed_blocks=counts[1])
        return state

    selected = []
    renderer.selected_pages = selected
    target = SimpleNamespace(screenshot=screenshot)
    page = SimpleNamespace(goto=AsyncMock(), evaluate=evaluate,
                           locator=lambda selector: SimpleNamespace(nth=lambda index: selected.append(index) or target))
    context = SimpleNamespace(route=AsyncMock(), new_page=AsyncMock(return_value=page), close=AsyncMock())
    renderer._browser = SimpleNamespace(new_context=AsyncMock(return_value=context))
    monkeypatch.setattr(renderer, '_start', AsyncMock())
    monkeypatch.setattr(renderer, '_font', lambda: None)
    monkeypatch.setattr(renderer, 'cache_key', lambda *args: 'fixture-key')
    now = datetime.fromisoformat('2026-10-15T12:00:00+08:00')
    snapshot = calendar_snapshot({'nte': QueryResult([], now.isoformat(), 'ok', True)}, now)
    result = QueryResult({'render_snapshot': snapshot}, now.isoformat(), 'ok', True)
    return renderer, context, result, calls, outputs


@pytest.mark.parametrize(('sizes', 'expected_key', 'qualities'), [
    ({'png': 200}, 'png', []),
    ({'png': 676, 90: 200}, 90, [90]),
    ({'png': 676, 90: 360, 85: 240}, 85, [90, 85]),
    ({'png': 676, 90: 360, 85: 310, 80: 280}, 80, [90, 85, 80]),
    ({'png': 700, 90: 900, 85: 800, 80: 850}, 'png', [90, 85, 80]),
])
async def test_large_png_targets_upload_budget_without_changing_geometry_or_rejecting_soft_miss(
        monkeypatch, sizes, expected_key, qualities):
    renderer, context, result, calls, outputs = renderer_boundary(monkeypatch, sizes)
    image = await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert image == outputs[expected_key]
    assert calls == [{'type': 'png', 'animations': 'disabled'}] + [
        {'type': 'jpeg', 'quality': quality, 'animations': 'disabled'} for quality in qualities]
    assert image.total_pages == 1 and image.page == 1
    with Image.open(BytesIO(image)) as decoded:
        assert decoded.size == (720, 100)
        assert decoded.format == ('PNG' if expected_key == 'png' else 'JPEG')
    context.close.assert_awaited_once()


async def test_upload_soft_budget_does_not_relax_hard_byte_limit(monkeypatch):
    renderer, context, result, calls, _ = renderer_boundary(
        monkeypatch, {'png': 676, 90: 350, 85: 320, 80: 310}, hard_kib=300)
    with pytest.raises(RenderingUnavailable, match='^qq_image_size_limit$'):
        await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert len(calls) == 4
    context.close.assert_awaited_once()


@pytest.mark.parametrize('height', [1441, 16001])
async def test_upload_encoding_does_not_bypass_pixel_or_height_limit(monkeypatch, height):
    renderer, context, result, calls, _ = renderer_boundary(monkeypatch, {'png': 200}, height=height)
    with pytest.raises(RenderingUnavailable, match='^qq_image_pixel_limit$'):
        await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert calls == []
    context.close.assert_awaited_once()


@pytest.mark.parametrize('page', [1, 2, 100])
async def test_only_requested_complete_short_page_is_captured(monkeypatch, page):
    pages = [{'width': 720, 'height': 100}] * 100
    renderer, context, result, calls, _ = renderer_boundary(monkeypatch, {'png': 200}, pages=pages)
    result.payload['render_snapshot']['page'] = page
    image = await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert (image.page, image.total_pages) == (page, 100)
    assert renderer.selected_pages == [page - 1] and len(calls) == 1
    renderer._browser.new_context.assert_awaited_once_with(
        viewport={'width': 720, 'height': 1440}, device_scale_factor=1,
        locale='zh-CN', timezone_id='Asia/Shanghai', reduced_motion='reduce',
        service_workers='block', accept_downloads=False)
    context.close.assert_awaited_once()


@pytest.mark.parametrize('pages,code', [
    ([], 'qq_browser_page_limit'),
    ([{'width': 720, 'height': 100}] * 101, 'qq_browser_page_limit'),
    ([{'width': 720, 'height': 100}, {'width': 720, 'height': 1441}], 'qq_image_pixel_limit'),
    ([{'width': 1080, 'height': 100}], 'qq_image_pixel_limit'),
    ([{'width': 720, 'height': 0}], 'qq_image_pixel_limit'),
    ([{'width': 720, 'height': True}], 'qq_image_pixel_limit'),
])
async def test_invalid_unselected_page_or_page_count_rejects_whole_render(monkeypatch, pages, code):
    renderer, context, result, calls, _ = renderer_boundary(monkeypatch, {'png': 200}, pages=pages)
    with pytest.raises(RenderingUnavailable, match=f'^{code}$'):
        await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert calls == []
    context.close.assert_awaited_once()


@pytest.mark.parametrize('counts', [(3, 2), (-1, -1), (True, True), (None, None)])
async def test_incomplete_content_never_returns_even_a_valid_first_page(monkeypatch, counts):
    renderer, context, result, calls, _ = renderer_boundary(monkeypatch, {'png': 200}, counts=counts)
    with pytest.raises(RenderingUnavailable, match='^qq_browser_shared_content_incomplete$'):
        await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert calls == []
    context.close.assert_awaited_once()


async def test_out_of_range_page_reports_actual_total_without_capture(monkeypatch):
    renderer, context, result, calls, _ = renderer_boundary(monkeypatch, {'png': 200},
        pages=[{'width': 720, 'height': 100}] * 2)
    result.payload['render_snapshot']['page'] = 3
    with pytest.raises(RenderingPageUnavailable) as error:
        await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert (error.value.page, error.value.total_pages) == (3, 2) and calls == []
    context.close.assert_awaited_once()


@pytest.mark.parametrize('dimensions', [(720, 101), (720, 99), (719, 100)])
async def test_browser_screenshot_must_match_selected_page_dimensions(monkeypatch, dimensions):
    renderer, context, result, calls, _ = renderer_boundary(monkeypatch, {'png': 200}, dimensions=dimensions)
    with pytest.raises(RenderingUnavailable, match='^qq_image_pixel_limit$'):
        await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert len(calls) == 1
    context.close.assert_awaited_once()


async def test_near_deadline_retains_complete_png_without_starting_optional_capture(monkeypatch):
    renderer, context, result, calls, outputs = renderer_boundary(
        monkeypatch, {'png': 676, 90: 200}, delay_jpeg=True)
    image = await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=.02)
    assert image == outputs['png']
    assert len(calls) == 1
    context.close.assert_awaited_once()


@pytest.mark.parametrize('delay', [True, 'error', 85])
async def test_optional_jpeg_timeout_or_failure_retains_complete_candidate(monkeypatch, delay):
    sizes = {'png': 676, 90: 360, 85: 200} if delay == 85 else {'png': 676, 90: 200}
    renderer, context, result, calls, outputs = renderer_boundary(
        monkeypatch, sizes, delay_jpeg=delay)
    image = await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=.2)
    assert image == outputs[90 if delay == 85 else 'png']
    assert len(calls) == (3 if delay == 85 else 2)
    assert image.total_pages == 1
    context.close.assert_awaited_once()


async def test_real_short_calendar_browser_encodings_keep_selected_page_geometry(monkeypatch):
    from playwright.async_api import Locator
    from tests.test_qq_browser_rendering import browser, calendar, envelope, SCOPE

    renderer = browser()
    original = Locator.screenshot
    captures = []

    async def screenshot(locator, **options):
        image = await original(locator, **options)
        with Image.open(BytesIO(image)) as decoded:
            captures.append((options['type'], len(image), decoded.size))
        return image

    monkeypatch.setattr(Locator, 'screenshot', screenshot)
    try:
        image = await renderer.render_summary_async(SCOPE, envelope(calendar(30)), budget_seconds=10)
        assert captures[0][0] == 'png'
        assert 1 <= len(captures) <= 4
        assert len({capture[2] for capture in captures}) == 1
        with Image.open(BytesIO(image)) as decoded:
            assert decoded.size == captures[0][2]
            assert decoded.width == 720 and 0 < decoded.height <= 1440
        assert image.total_pages > 1 and image.page == 1 and len(image) <= renderer.max_bytes
        assert renderer.last_state['content_blocks'] == renderer.last_state['displayed_blocks']
        assert not renderer._browser.contexts
    finally:
        await renderer.aclose()


async def test_another_accounts_change_mid_render_still_returns_the_image(monkeypatch):
    # Any account change bumps the renderer's shared generation. The query service
    # re-checks this user's binding and grants after rendering, so the image is kept
    # for this reply; only caching it would be unsafe.
    renderer, context, result, calls, outputs = renderer_boundary(monkeypatch, {'png': 200})
    renderer.cache_entries = 16
    page = context.new_page.return_value
    evaluate = page.evaluate
    async def evaluate_while_another_account_changes(expression, input=None):
        state = await evaluate(expression, input)
        if input is None:
            renderer.invalidate_account('another-user')
        return state
    page.evaluate = evaluate_while_another_account_changes
    image = await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert image == outputs['png'] and len(renderer.cache) == 0
    page.evaluate = evaluate
    await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert len(renderer.cache) == 1


async def test_cached_images_are_keyed_per_user_and_dropped_with_any_scoped_account(monkeypatch, tmp_path):
    renderer, context, result, calls, outputs = renderer_boundary(monkeypatch, {'png': 200})
    (tmp_path / 'render.html').write_text('<!doctype html>')
    renderer.dist = tmp_path
    monkeypatch.setattr(renderer, 'cache_key', BrowserRenderer.cache_key.__get__(renderer))
    renderer.cache_entries = 2
    scopes = [{'account_id': 'a', 'role_id': 'r', 'grant_version': 1}, {'account_id': 'b', 'role_id': 's', 'grant_version': 1}]
    shared = QueryResult({**result.payload, 'text': '同一份数据', 'scopes': scopes}, result.fetched_at, result.state, result.complete)
    for user in ('u', 'v', 'w'):
        await renderer.render_summary_async(AccountScope(user, 'a', 'r'), shared, budget_seconds=10)
    # Identical display data never reaches another user through the cache.
    assert len(calls) == 3 and len(renderer.cache) == 2
    assert [owner for owner, _, _ in renderer.cache.values()] == [('v', frozenset('ab')), ('w', frozenset('ab'))]
    renderer.invalidate_account('w', 'c')
    assert len(renderer.cache) == 2
    renderer.invalidate_account('w', 'b')
    assert [owner[0] for owner, _, _ in renderer.cache.values()] == ['v']


@pytest.mark.parametrize('page', [1, 2, 3])
async def test_query_reply_reports_image_pages_with_complete_input_and_valid_next_command(page):
    from game_assistant.qq.query_routes import QqQueryService
    from game_assistant.qq.models import QqIdentity
    from game_assistant.qq.rendering import RenderedImage
    from game_assistant.qq.commands import parse_command
    from tests.test_qq_browser_rendering import calendar, NOW

    observed=[]
    class Queue:
        async def render(self, scope, result, *, budget_seconds):
            snapshot=result.payload['render_snapshot']
            observed.append(snapshot)
            return RenderedImage(encoded_image('PNG', 20), page=snapshot['page'], total_pages=3)
    events=calendar(70)['display_data']['snapshots']['nte']['events']['payload']
    service=QqQueryService(None,None,SimpleNamespace(read=lambda game,cap:QueryResult(events,NOW.isoformat(),'ok',False)),
        render_queue=Queue(),clock=lambda:NOW)
    identity=QqIdentity('app','group','g','s')
    original=service.query(identity,'calendar','nte')['text']
    response=await service.query_reply(identity,'calendar','nte',image_requested=True,budget_seconds=10,page=page)
    assert 'image' in response and response['page']==page and response['total_pages']==3
    assert observed[0]['page']==page
    assert len(observed[0]['display_data']['snapshots']['nte']['events']['payload'])==70
    assert response['text'].startswith(original)
    assert '无需翻页' not in response['text']
    assert f'第 {page} / 3 页' in response['text']
    if page<3:
        command=response['text'].split('下一页：')[1]
        parsed=parse_command(command)
        assert parsed.page==page+1 and parsed.game=='nte' and parsed.command=='calendar'
    else:assert '下一页：' not in response['text']


async def test_browser_cache_key_includes_selected_page(monkeypatch, tmp_path):
    renderer, _, result, _, _=renderer_boundary(monkeypatch, {'png':200})
    (tmp_path/'render.html').write_text('<!doctype html>')
    renderer.dist=tmp_path
    monkeypatch.setattr(renderer, 'cache_key', BrowserRenderer.cache_key.__get__(renderer))
    scope=AccountScope('u','a','r')
    result.payload['text']='完整摘要'
    first=renderer.cache_key(scope,result)
    result.payload['render_snapshot']['page']=2
    assert renderer.cache_key(scope,result)!=first


async def test_short_page_at_exact_height_limit_is_accepted_without_resizing(monkeypatch):
    renderer, context, result, calls, _=renderer_boundary(monkeypatch, {'png':200}, height=1440, dimensions=(720,1440))
    image=await renderer.render_summary_async(AccountScope('u','a','r'),result,budget_seconds=10)
    with Image.open(BytesIO(image)) as decoded:assert decoded.size==(720,1440)
    assert len(calls)==1
    context.close.assert_awaited_once()


async def test_short_pages_do_not_relax_configured_pixel_limit(monkeypatch):
    renderer, context, result, calls, _=renderer_boundary(monkeypatch, {'png':200})
    renderer.max_pixels=720*99
    with pytest.raises(RenderingUnavailable, match='^qq_image_pixel_limit$'):
        await renderer.render_summary_async(AccountScope('u','a','r'),result,budget_seconds=10)
    assert calls==[]
    context.close.assert_awaited_once()

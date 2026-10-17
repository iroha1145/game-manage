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
from game_assistant.qq.rendering import RenderingUnavailable


def encoded_image(format, size_kib, *, quality=90):
    output = BytesIO()
    Image.new('RGB', (1080, 100), '#f5f5f5').save(output, format, **({'quality': quality} if format == 'JPEG' else {}))
    # Padding after the encoded image controls byte budgets without huge fixtures.
    return output.getvalue().ljust(size_kib * 1024, b'\0')


def renderer_boundary(monkeypatch, sizes, *, hard_kib=1024, height=100, delay_jpeg=False):
    renderer = BrowserRenderer(cache_entries=0, max_bytes=hard_kib * 1024)
    calls = []
    outputs = {key: encoded_image('PNG' if key == 'png' else 'JPEG', size,
                                 quality=key if isinstance(key, int) else 90)
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
                         pages=[{'width': 1080, 'height': height}])
        return state

    target = SimpleNamespace(screenshot=screenshot)
    page = SimpleNamespace(goto=AsyncMock(), evaluate=evaluate,
                           locator=lambda selector: SimpleNamespace(nth=lambda index: target))
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
        assert decoded.size == (1080, 100)
        assert decoded.format == ('PNG' if expected_key == 'png' else 'JPEG')
    context.close.assert_awaited_once()


async def test_upload_soft_budget_does_not_relax_hard_byte_limit(monkeypatch):
    renderer, context, result, calls, _ = renderer_boundary(
        monkeypatch, {'png': 676, 90: 350, 85: 320, 80: 310}, hard_kib=300)
    with pytest.raises(RenderingUnavailable, match='^qq_image_size_limit$'):
        await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert len(calls) == 4
    context.close.assert_awaited_once()


@pytest.mark.parametrize('height', [15000, 16001])
async def test_upload_encoding_does_not_bypass_pixel_or_height_limit(monkeypatch, height):
    renderer, context, result, calls, _ = renderer_boundary(monkeypatch, {'png': 200}, height=height)
    with pytest.raises(RenderingUnavailable, match='^qq_image_pixel_limit$'):
        await renderer.render_summary_async(AccountScope('u', 'a', 'r'), result, budget_seconds=10)
    assert calls == []
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


async def test_real_large_calendar_uses_smaller_browser_jpeg_with_complete_geometry(monkeypatch):
    from playwright.async_api import Locator
    from tests.test_qq_browser_rendering import browser, calendar, envelope, SCOPE

    renderer = browser()
    original = Locator.screenshot
    captures = []

    async def screenshot(locator, **options):
        if options['type'] == 'png':
            assert await locator.locator('.event-lane').count() == 30
            text = await locator.inner_text()
            assert '活动 000' in text and '活动 029' in text
        image = await original(locator, **options)
        with Image.open(BytesIO(image)) as decoded:
            captures.append((options['type'], len(image), decoded.size))
        return image

    monkeypatch.setattr(Locator, 'screenshot', screenshot)
    try:
        image = await renderer.render_summary_async(SCOPE, envelope(calendar(30)), budget_seconds=10)
        assert captures[0][0] == 'png' and captures[0][1] > 256 * 1024
        assert image.startswith(b'\xff\xd8') and len(image) < captures[0][1]
        assert 2 <= len(captures) <= 4
        assert len({capture[2] for capture in captures}) == 1
        with Image.open(BytesIO(image)) as decoded:
            assert decoded.size == captures[0][2]
            assert decoded.width == 1080 and decoded.height > 1000
        assert image.total_pages == 1 and len(image) <= renderer.max_bytes
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

"""Bounded private PNG rendering from validated display documents or legacy text.

No remote assets or disk cache. Fonts are operator-provided system fonts;
Ubuntu operators can install fonts-noto-cjk. Windows fonts are never bundled.
"""
import asyncio
from collections import OrderedDict
import hashlib
from io import BytesIO
import json
import re
from pathlib import Path
import threading
import time

from PIL import Image, ImageDraw, ImageFont

from game_assistant.accounts.models import AccountScope, QueryResult
from .commands import safe_text
from .cards import validate_card_document, card_to_text, image_references
from . import card_rendering

TEMPLATE_VERSION = 'qq-unified-3-endfield-6'


class RenderingUnavailable(Exception):
    """Known pre-send failure: the caller may safely use its text reply."""


class RenderingPageUnavailable(RenderingUnavailable):
    def __init__(self, page, total_pages):
        self.page, self.total_pages = page, total_pages
        super().__init__('qq_browser_page_out_of_range')


class RenderedImage(bytes):
    def __new__(cls, value, *, page=1, total_pages=1):
        result=super().__new__(cls,value)
        result.page,result.total_pages=page,total_pages
        return result


class ImagePreparationFailed(Exception):
    """No message send was attempted; a text reply with the same sequence is safe."""


class SummaryRenderer:
    def __init__(self, *, font_path='', max_bytes=1048576, cache_entries=16, cache_ttl=120,
                 max_pixels=16000000, budget_seconds=8, asset_cache=None):
        self.font_path = font_path
        self.max_bytes = max(1,min(max_bytes,1048576))
        self.max_pixels = max(1, min(max_pixels, 16000000))
        self.asset_cache = asset_cache
        self.budget_seconds = max(0.001, min(budget_seconds, 10))
        self.cache_entries = max(0, min(cache_entries, 32))
        self.cache_ttl = max(0, min(cache_ttl, 300))
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.generation = 0

    def _payload(self, result):
        payload = result.payload
        if not isinstance(payload, dict) or set(payload) - {'text', 'card', 'render_snapshot', 'shared_required', 'grant_version', 'snapshot_times', 'scopes', 'snapshot_fingerprints'}:
            raise RenderingUnavailable('qq_image_safe_summary_required')
        payload = dict(payload)
        if 'card' in payload:
            try:
                payload['card'] = validate_card_document(payload['card'])
                text = card_to_text(payload['card'])
            except (ValueError, TypeError):
                raise RenderingUnavailable('qq_image_safe_summary_required') from None
            if 'text' in payload and payload['text'] != text:
                raise RenderingUnavailable('qq_image_text_card_mismatch')
            payload['text'] = text
        else:
            text = payload.get('text')
            if not isinstance(text, str) or not text or len(text) > 1800:
                raise RenderingUnavailable('qq_image_safe_summary_required')
            payload['text'] = safe_text(text)
        grant_version = payload.get('grant_version')
        if grant_version is not None and (type(grant_version) is not int or grant_version < 1):
            raise RenderingUnavailable('qq_image_safe_summary_required')
        times = payload.get('snapshot_times', [])
        if not isinstance(times, list) or len(times) > 24 or any(t is not None and (not isinstance(t, str) or len(t)>128) for t in times):
            raise RenderingUnavailable('qq_image_safe_summary_required')
        scopes = payload.get('scopes', [])
        if not isinstance(scopes,list) or len(scopes)>4:
            raise RenderingUnavailable('qq_image_safe_summary_required')
        for item in scopes:
            if (not isinstance(item,dict) or set(item)!={'account_id','role_id','grant_version'}
                or any(not isinstance(item[k],str) or not 1<=len(item[k])<=256 for k in ('account_id','role_id'))
                or type(item['grant_version']) is not int or item['grant_version']<1):
                raise RenderingUnavailable('qq_image_safe_summary_required')
        fingerprints = payload.get('snapshot_fingerprints', [])
        if (not isinstance(fingerprints,list) or len(fingerprints)>24
            or any(not isinstance(f,str) or not re.fullmatch('[0-9a-f]{64}',f) for f in fingerprints)):
            raise RenderingUnavailable('qq_image_safe_summary_required')
        return payload

    def cache_key(self, scope: AccountScope, result: QueryResult):
        payload = self._payload(result)
        fingerprint = [scope.user_id, scope.account_id, scope.role_id, payload,
                       result.fetched_at, result.state, result.complete,
                       TEMPLATE_VERSION, self.font_path, self.max_bytes, self.max_pixels, self.budget_seconds]
        if 'card' in payload:
            fingerprint.append([(ref,self.asset_cache.fingerprint(ref) if self.asset_cache is not None else 'missing')
                                for ref in image_references(payload['card'])])
        return hashlib.sha256(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def invalidate_account(self, user_id, account_id=None):
        with self.lock:
            self.generation += 1
            for key, (owner, _, _) in list(self.cache.items()):
                if owner[0] == user_id and (account_id is None or account_id in owner[1]):
                    del self.cache[key]

    def _font(self):
        # Explicit path only: absence produces text, never unreadable tofu glyphs.
        path = Path(self.font_path)
        if not self.font_path or not path.is_absolute() or not path.is_file():
            raise RenderingUnavailable('qq_image_cjk_font_unavailable')
        try:
            # The standard Noto CJK TTC orders JP, KR, SC, TC, HK faces.
            index = 2 if path.name == 'NotoSansCJK-Regular.ttc' else 0
            font = ImageFont.truetype(str(path), 30,index=index)
            tofu = bytes(font.getmask('\uffff'))
            if any(bytes(font.getmask(c)) == tofu for c in '鸣潮未知账号等级'):
                raise ValueError()
            return font
        except Exception:
            raise RenderingUnavailable('qq_image_cjk_font_unavailable') from None

    def render_summary(self, scope: AccountScope, result: QueryResult) -> bytes:
        key = self.cache_key(scope, result)
        with self.lock:
            now = time.monotonic()
            for expired, (_, expiry, _) in list(self.cache.items()):
                if expiry <= now:
                    del self.cache[expired]
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key][2]
            generation = self.generation
        font = self._font()
        payload = self._payload(result)
        if 'card' in payload:
            try:
                png = card_rendering.render_card(payload['card'],font=font,max_bytes=self.max_bytes,
                    max_pixels=self.max_pixels,budget_seconds=self.budget_seconds,asset_cache=self.asset_cache)
            except ValueError as error:
                raise RenderingUnavailable(str(error)) from None
        else:
            png = self._render_text(payload['text'],font)
        with self.lock:
            if self.generation != generation:
                return png
            if self.cache_entries:
                accounts = frozenset([scope.account_id]+[s['account_id'] for s in payload.get('scopes',[])])
                owner = (scope.user_id, accounts)
                self.cache[key] = (owner, time.monotonic() + self.cache_ttl, png)
                while len(self.cache) > self.cache_entries:
                    self.cache.popitem(last=False)
        return png

    def _render_text(self, text, font):
        started = time.monotonic()
        # The owned template is simple text on a card, with hard pixel bounds.
        lines = []
        for paragraph in text.split('\n'):
            current = ''
            for char in paragraph:
                if font.getlength(current + char) > 996:
                    lines.append(current)
                    current = ''
                current += char
            lines.append(current)
        if len(lines) > 64:
            raise RenderingUnavailable('qq_image_summary_too_long')
        height = max(160,72+len(lines)*44)
        if height>2400 or 1080*height>self.max_pixels:
            raise RenderingUnavailable('qq_image_pixel_limit')
        image = Image.new('RGB', (1080, height), '#f5f7fb')
        draw = ImageDraw.Draw(image)
        for index, line in enumerate(lines):
            draw.text((42, 30 + index * 44), line, font=font, fill='#172235')
        output = BytesIO()
        image.save(output, format='PNG', optimize=True)
        png = output.getvalue()
        if len(png) > self.max_bytes:
            raise RenderingUnavailable('qq_image_size_limit')
        if time.monotonic()-started>self.budget_seconds:
            raise RenderingUnavailable('qq_image_time_limit')
        return png


class RenderQueue:
    """One worker, up to ten admitted requests, with strict caller deadlines.

Timed-out CPU work keeps its slot until the worker really finishes. Cancelling
the HTTP request never causes a second thread to render concurrently.
"""
    def __init__(self, renderer, *, queue_limit=10):
        self.renderer = renderer
        self.queue_limit = max(1, min(queue_limit, 10))
        self.pending = 0
        self.lock = asyncio.Semaphore(1)
        self.tasks = set()

    async def render(self, scope, result, *, budget_seconds):
        if budget_seconds <= 0 or self.pending >= self.queue_limit:
            return None
        expires = time.monotonic() + min(budget_seconds, 10)
        self.pending += 1
        async def work():
            try:
                async with self.lock:
                    if time.monotonic() >= expires:
                        return None
                    try:
                        if hasattr(self.renderer, 'render_summary_async'):
                            return await self.renderer.render_summary_async(scope, result, budget_seconds=max(0, expires-time.monotonic()))
                        return await asyncio.to_thread(self.renderer.render_summary, scope, result)
                    except RenderingPageUnavailable as error:
                        return error
                    except RenderingUnavailable as error:
                        return error if str(error) in ('qq_image_size_limit','qq_image_pixel_limit') else None
                    except Exception:
                        return None
            finally:
                self.pending -= 1
        task = asyncio.create_task(work())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=max(0, expires - time.monotonic()))
        except asyncio.TimeoutError:
            return None

    async def aclose(self):
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)
        if hasattr(self.renderer, 'aclose'):
            await self.renderer.aclose()


def render_summary(scope: AccountScope, result: QueryResult) -> bytes:
    """Canonical sync interface; service callers use a configured RenderQueue."""
    from game_assistant.config import Settings
    settings = Settings.load()
    return SummaryRenderer(font_path=settings.qq_image_font_path,
                           max_bytes=settings.qq_image_max_bytes).render_summary(scope, result)

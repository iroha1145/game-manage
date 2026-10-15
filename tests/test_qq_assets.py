"""Public-image security and cache contracts; no private upstream is contacted."""
import asyncio
import hashlib
from io import BytesIO
from pathlib import Path
import socket

from PIL import Image
import pytest


def module():
    from game_assistant.qq import assets
    return assets


def png(size=(32, 48), color='red'):
    out = BytesIO()
    Image.new('RGBA', size, color).save(out, 'PNG')
    return out.getvalue()


@pytest.mark.parametrize('url', [
    'http://webstatic.tajiduo.com/a.png',
    'https://webstatic.tajiduo.com.evil.example/a.png',
    'https://u:p@webstatic.tajiduo.com/a.png',
    'https://webstatic.tajiduo.com/a.png?token=secret',
    'https://webstatic.tajiduo.com/a.png#x',
    'https://webstatic.tajiduo.com:444/a.png',
    'https://127.0.0.1/a.png', 'file:///a.png',
    'https://webstatic.tajiduo.com/a.svg',
    'https://webstatic.tajiduo.com/a%0d%0a.png',
    'https://webstatic.tajiduo.com/a.png\r\nCookie: bad',
    'https://webstatic.tajiduo.com/%2e%2e/a.png',
])
def test_untrusted_urls_rejected(url):
    assert module().PublicAssetCache().register_url(url) is None


def test_refs_catalog_and_no_network_getter():
    cache = module().PublicAssetCache()
    url = 'https://webstatic.tajiduo.com/bbs/pic/player_003_256.png'
    ref = cache.register_url(url)
    assert ref == 'qqasset_' + hashlib.sha256(url.encode()).hexdigest()
    assert cache.ref_for('nte', 'role', '早雾') == ref
    assert cache.ref_for('nte', 'role', '1003') == ref
    assert cache.ref_for('wuthering_waves', 'weapon', '苍鳞千嶂')
    assert cache.ref_for('nte', 'weapon', '光波眩晕')
    assert cache.ref_for('nte', 'role', '不存在') is None
    assert cache.get_image(ref) is None
    assert cache.fingerprint(ref) == 'missing'


def test_endfield_public_catalog_and_exact_cdn_hosts():
    from game_assistant.qq.public_asset_catalog import CATALOG
    cache = module().PublicAssetCache()
    roles = CATALOG['games']['endfield']['role']
    assert len(set(roles.values())) == 35
    assert cache.ref_for('endfield', 'role', '佩丽卡') == cache.ref_for('endfield', 'role', 'perlica')
    assert cache.ref_for('endfield', 'role', '祀')
    # The official site has two portraits called 管理员; a name alone is insufficient.
    assert cache.ref_for('endfield', 'role', '管理员') is None
    assert cache.ref_for('endfield', 'role', 'endministrator1') != cache.ref_for('endfield', 'role', 'endministrator2')
    assert cache.register_url('https://bbs.hycdn.cn/public/skland-web/image/example.png')
    for url in ('https://web.hycdn.cn.evil.example/a.png',
                'https://web.hycdn.cn/a.png?token=private',
                'https://bbs.hycdn.cn/%2e%2e/a.png',
                'https://web.hycdn.cn/a.svg',
                'https://ak.hycdn.cn/a.png'):
        assert cache.register_url(url) is None


async def test_cache_sanitizes_and_reuses(monkeypatch):
    assets = module()
    calls = []
    async def fetch(url, **kwargs):
        calls.append(url)
        return png((300, 200))
    monkeypatch.setattr(assets, '_download', fetch)
    cache = assets.PublicAssetCache()
    ref = cache.register_url('https://webstatic.tajiduo.com/a.png')
    await cache.prefetch([ref, ref], budget_seconds=1)
    image = cache.get_image(ref)
    assert image.mode == 'RGBA' and max(image.size) == 192
    image.putpixel((0, 0), (0, 0, 0, 0))
    assert cache.get_image(ref).getpixel((0, 0)) != (0, 0, 0, 0)
    assert len(cache.fingerprint(ref)) == 64
    await cache.prefetch([ref], budget_seconds=1)
    assert len(calls) == 1


async def test_bad_decode_falls_back_and_retries_are_bounded(monkeypatch):
    assets = module()
    calls = []
    async def fetch(url, **kwargs):
        calls.append(url)
        return b'<svg><script>evil()</script></svg>'
    monkeypatch.setattr(assets, '_download', fetch)
    cache = assets.PublicAssetCache()
    ref = cache.register_url('https://webstatic.tajiduo.com/a.png')
    await cache.prefetch([ref], budget_seconds=.5)
    await cache.prefetch([ref], budget_seconds=.5)
    assert cache.get_image(ref) is None
    assert len(calls) == 1


def test_sanitizer_rejects_pixel_bomb_and_animated_webp():
    assets = module()
    with pytest.raises(ValueError):
        assets.sanitize_image(png((2100, 2100)))
    out = BytesIO()
    Image.new('RGB', (32, 32), 'red').save(out, 'WEBP', save_all=True,
        append_images=[Image.new('RGB', (32, 32), 'blue')], duration=50, loop=0)
    with pytest.raises(ValueError):
        assets.sanitize_image(out.getvalue())


async def test_lru_and_ttl(monkeypatch):
    assets = module()
    clock = [1.0]
    monkeypatch.setattr(assets.time, 'monotonic', lambda: clock[0])
    async def fetch(url, **kwargs):
        return png()
    monkeypatch.setattr(assets, '_download', fetch)
    cache = assets.PublicAssetCache(cache_entries=1, cache_ttl=5)
    first = cache.register_url('https://webstatic.tajiduo.com/first.png')
    second = cache.register_url('https://webstatic.tajiduo.com/second.png')
    await cache.prefetch([first], budget_seconds=.5)
    await cache.prefetch([second], budget_seconds=.5)
    assert cache.get_image(first) is None and cache.get_image(second)
    clock[0] = 7
    assert cache.get_image(second) is None


async def test_bounded_concurrency_and_cancellation(monkeypatch):
    assets = module()
    active = 0
    maximum = 0
    async def fetch(url, **kwargs):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        try:
            await asyncio.sleep(.2)
            return png()
        finally:
            active -= 1
    monkeypatch.setattr(assets, '_download', fetch)
    cache = assets.PublicAssetCache(concurrency=2)
    refs = [cache.register_url(f'https://webstatic.tajiduo.com/{i}.png') for i in range(40)]
    await cache.prefetch(refs, budget_seconds=.03)
    assert maximum <= 2 and active == 0
    assert not cache._inflight


async def test_private_dns_rejected_before_connection(monkeypatch):
    assets = module()
    loop = asyncio.get_running_loop()
    async def dns(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
    monkeypatch.setattr(loop, 'getaddrinfo', dns)
    async def connect(*args, **kwargs):
        pytest.fail('private DNS must never connect')
    monkeypatch.setattr(assets.asyncio, 'open_connection', connect)
    with pytest.raises(ValueError):
        await assets._download('https://webstatic.tajiduo.com/a.png', timeout_seconds=.5)


@pytest.mark.parametrize('bad_ip', ['10.0.0.1', '169.254.169.254', '198.18.0.1',
    '224.0.0.1', '::1', '::ffff:127.0.0.1', 'fe80::1'])
async def test_mixed_dns_answers_are_all_vetted(monkeypatch, bad_ip):
    assets = module()
    loop = asyncio.get_running_loop()
    async def dns(*args, **kwargs):
        family = socket.AF_INET6 if ':' in bad_ip else socket.AF_INET
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('1.1.1.1', 443)),
                (family, socket.SOCK_STREAM, 6, '', (bad_ip, 443))]
    monkeypatch.setattr(loop, 'getaddrinfo', dns)
    async def connect(*args, **kwargs):
        pytest.fail('a mixed public and unsafe DNS answer must never connect')
    monkeypatch.setattr(assets.asyncio, 'open_connection', connect)
    with pytest.raises(ValueError):
        await assets._download('https://webstatic.tajiduo.com/a.png', timeout_seconds=.5)


async def test_tls_connection_uses_pinned_ip_and_no_secrets(monkeypatch):
    assets = module()
    loop = asyncio.get_running_loop()
    async def dns(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('1.1.1.1', 443))]
    monkeypatch.setattr(loop, 'getaddrinfo', dns)
    body = png()
    reader = asyncio.StreamReader()
    reader.feed_data(b'HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
    reader.feed_eof()
    class Writer:
        request = b''
        def write(self, data): self.request += data
        async def drain(self): pass
        def close(self): pass
    writer = Writer()
    async def connect(host, port, **kwargs):
        assert host == '1.1.1.1' and port == 443
        assert kwargs['server_hostname'] == 'webstatic.tajiduo.com'
        assert kwargs['ssl'].check_hostname
        return reader, writer
    monkeypatch.setattr(assets.asyncio, 'open_connection', connect)
    assert await assets._download('https://webstatic.tajiduo.com/a.png', timeout_seconds=.5) == body
    assert b'Host: webstatic.tajiduo.com\r\n' in writer.request
    assert b'Authorization' not in writer.request and b'Cookie' not in writer.request


@pytest.mark.parametrize('headers', [
    b'HTTP/1.1 302 Found\r\nLocation: https://127.0.0.1/a.png\r\n\r\n',
    b'HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: 99999999\r\n\r\n',
    b'HTTP/1.1 200 OK\r\nContent-Type: image/svg+xml\r\n\r\n',
])
async def test_redirect_and_oversized_http_rejected(monkeypatch, headers):
    assets = module()
    loop = asyncio.get_running_loop()
    async def dns(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('1.1.1.1', 443))]
    monkeypatch.setattr(loop, 'getaddrinfo', dns)
    reader = asyncio.StreamReader()
    reader.feed_data(headers)
    reader.feed_eof()
    class Writer:
        def write(self, data): pass
        async def drain(self): pass
        def close(self): pass
    async def connect(*args, **kwargs): return reader, Writer()
    monkeypatch.setattr(assets.asyncio, 'open_connection', connect)
    with pytest.raises(ValueError):
        await assets._download('https://webstatic.tajiduo.com/a.png', timeout_seconds=.5)


async def test_chunked_size_and_unbounded_body_are_capped():
    assets = module()
    chunked = asyncio.StreamReader()
    chunked.feed_data(b'400000\r\n')
    chunked.feed_eof()
    with pytest.raises(ValueError):
        await assets._read_body(chunked, {'transfer-encoding':'chunked'})
    raw = asyncio.StreamReader()
    raw.feed_data(b'X' * (assets.MAX_DOWNLOAD_BYTES + 1))
    raw.feed_eof()
    with pytest.raises(ValueError):
        await assets._read_body(raw, {})


async def test_inflight_request_is_shared_and_local_emblems_are_real_images(monkeypatch):
    assets = module()
    calls = []
    async def fetch(url, **kwargs):
        calls.append(url)
        await asyncio.sleep(.02)
        return png()
    monkeypatch.setattr(assets, '_download', fetch)
    cache = assets.PublicAssetCache()
    ref = cache.register_url('https://webstatic.tajiduo.com/a.png')
    await asyncio.gather(cache.prefetch([ref], budget_seconds=.5), cache.prefetch([ref], budget_seconds=.5))
    assert len(calls) == 1
    for game in ('all','nte','wuthering_waves','endfield'):
        emblem = cache.ref_for(game, 'game', game)
        image = cache.get_image(emblem)
        assert image.size == (192, 192) and image.mode == 'RGBA'
        assert image.getpixel((0, 0))[3] == 0
    await cache.aclose()


def test_public_export_is_bound_to_existing_frontend_sources():
    from game_assistant.qq.public_asset_catalog import CATALOG, MANIFEST
    root = Path(__file__).resolve().parents[1]
    for source in MANIFEST['exports']:
        assert hashlib.sha256((root/source['file']).read_bytes().replace(b'\r\n',b'\n')).hexdigest() == source['sha256']
        assert source['sources']
    for game in CATALOG['games'].values():
        for entries in game.values():
            assert all(module().safe_public_url(url) is not None for url in entries.values())


async def test_cache_total_bytes_and_registry_are_bounded(monkeypatch):
    assets = module()
    async def fetch(url, **kwargs): return png()
    monkeypatch.setattr(assets, '_download', fetch)
    cache = assets.PublicAssetCache(cache_bytes=1)
    ref = cache.register_url('https://webstatic.tajiduo.com/a.png')
    await cache.prefetch([ref], budget_seconds=.5)
    assert cache.get_image(ref) is None and cache._bytes == 0
    for i in range(2100):
        cache.register_url(f'https://webstatic.tajiduo.com/{i}.png')
    assert len(cache._sources) == 2048


async def test_subsequent_prefetch_skips_cached_first_batch_and_completes_later_icons(monkeypatch):
    assets = module()
    calls = []
    async def fetch(url, **kwargs):
        calls.append(url)
        return png()
    monkeypatch.setattr(assets, '_download', fetch)
    cache = assets.PublicAssetCache(cache_entries=128)
    refs = [cache.register_url(f'https://webstatic.tajiduo.com/page-{i}.png') for i in range(100)]
    await cache.prefetch(refs, budget_seconds=1)
    assert sum(cache.get_image(ref) is not None for ref in refs) == 80
    await cache.prefetch(refs, budget_seconds=1)
    assert all(cache.get_image(ref) is not None for ref in refs)
    assert len(calls) == 100


async def test_reviewed_portraits_keep_detail_resolution_with_bounded_separate_cache(monkeypatch):
    assets = module()
    cache = assets.PublicAssetCache()
    portrait = cache.ref_for('endfield', 'portrait', '佩丽卡')
    assert portrait == cache.ref_for('endfield', 'portrait', 'perlica')
    assert cache.ref_for('endfield', 'portrait', '管理员') is None
    assert cache.register_url('https://bbs.hycdn.cn/unreviewed.png', portrait=True) is None
    url = cache._sources[portrait]
    ordinary = cache.register_url(url)
    assert portrait != ordinary
    async def fetch(url, **kwargs): return png((600, 800))
    monkeypatch.setattr(assets, '_download', fetch)
    await cache.prefetch([portrait, ordinary], budget_seconds=2)
    assert cache.get_image(portrait).size == (384, 512)
    assert cache.get_image(ordinary).size == (144, 192)
    assert cache._bytes <= cache.cache_bytes
    assert cache.fingerprint(portrait) != cache.fingerprint(ordinary)
    await cache.aclose()

"""Endfield dynamic loadout icons use the production safe-download pipeline."""
import asyncio
from io import BytesIO
import socket
import ssl

from PIL import Image

from game_assistant.accounts.models import QueryResult
from game_assistant.adapters.endfield.skland_parse import parse_card
from game_assistant.qq import assets
from game_assistant.qq.cards import image_references
from game_assistant.qq.endfield_presentation import operator_document


def source():
    def icon(kind):
        return f'https://bbs.hycdn.cn/public/skland-web/image/synthetic-{kind}.png'

    char = {'id': 'synthetic-instance', 'level': 80,
            'charData': {'id': 'synthetic-template', 'name': '合成干员',
                         'avatarSqUrl': icon('avatar'),
                         'skills': [{'id': f'skill-{index}', 'name': f'合成技能{index}',
                                     'iconUrl': icon(f'skill-{index}')} for index in range(4)]},
            'weapon': {'level': 80, 'weaponData': {'name': '合成武器', 'iconUrl': icon('weapon')},
                       'gem': {'gemData': {'name': '合成基质', 'icon': icon('gem')}}},
            'tacticalItem': {'tacticalItemData': {'name': '合成战术道具', 'iconUrl': icon('tactical')}}}
    for index, slot in enumerate(('bodyEquip', 'armEquip', 'firstAccessory', 'secondAccessory')):
        char[slot] = {'equipData': {'name': f'合成装备{index}', 'iconUrl': icon(slot)}}
    return {'chars': [char]}


async def test_all_twelve_dynamic_icons_are_downloaded_pinned_and_sanitized(monkeypatch):
    payload = parse_card(source(), fetched_at='2026-10-15T00:00:00+00:00')
    cache = assets.PublicAssetCache()
    card = operator_document(QueryResult(payload, '2026-10-15T00:00:00+00:00', 'ok', None),
                             '合成干员', cache)
    refs = set(image_references(card))
    assert len(refs) == 12
    assert all(ref in cache._sources for ref in refs)
    assert 'https://' not in str(card)
    section_counts = {section['category']: len(image_references({'sections': [section]}))
                      for section in card['sections'] if section.get('category')}
    assert section_counts['ef_weapon'] == section_counts['ef_gem'] == 1
    assert section_counts['ef_equipment'] == section_counts['ef_skills'] == 4
    assert section_counts['ef_tactical'] == 1

    async def dns(host, port, **kwargs):
        assert host == 'bbs.hycdn.cn' and port == 443
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('1.1.1.1', 443))]

    monkeypatch.setattr(asyncio.get_running_loop(), 'getaddrinfo', dns)
    output = BytesIO()
    Image.new('RGB', (300, 200), 'red').save(output, 'PNG')
    body = output.getvalue()
    requests = []

    class Writer:
        def write(self, data):
            requests.append(data)

        async def drain(self):
            pass

        def close(self):
            pass

    async def connect(host, port, **kwargs):
        assert (host, port) == ('1.1.1.1', 443)
        assert kwargs['server_hostname'] == 'bbs.hycdn.cn'
        assert kwargs['ssl'].check_hostname and kwargs['ssl'].verify_mode == ssl.CERT_REQUIRED
        reader = asyncio.StreamReader()
        reader.feed_data(b'HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: ' +
                         str(len(body)).encode() + b'\r\n\r\n' + body)
        reader.feed_eof()
        return reader, Writer()

    monkeypatch.setattr(assets.asyncio, 'open_connection', connect)
    await cache.prefetch(refs, budget_seconds=3)
    assert len(requests) == 12
    assert all(b'Host: bbs.hycdn.cn\r\n' in request for request in requests)
    assert all(b'Authorization:' not in request and b'Cookie:' not in request for request in requests)
    for ref in refs:
        image = cache.get_image(ref)
        assert image.mode == 'RGBA' and image.size == (192, 128)
    await cache.aclose()

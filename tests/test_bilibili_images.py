"""Images use the same verified source response as text, with no extra reads."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from game_assistant.sources.bilibili import BilibiliClient, SourceError, classify_dynamic, opus_content
from game_assistant.sources.public_content import parse_post_events
from tests.test_bilibili_source import UID, NOW, post

# Public opus paragraph structure observed on 2026-10-18, without account data.
HTTP_IMAGE = 'http://i0.hdslb.com/bfs/new_dyn/142523d4e14d0798078580892d98674d1955897084.jpg'
HTTPS_IMAGE = HTTP_IMAGE.replace('http:', 'https:', 1)


def detail():
    return {'item': {'id_str': '1', 'basic': {'uid': UID}, 'modules': [
        {'module_title': {'text': '1.4版本活动公告'}},
        {'module_content': {'paragraphs': [
            {'para_type': 1, 'text': {'nodes': [{'word': {'words':
                '● 「独立活动」限时活动\n活动时间：2026年9月15日05:00-2026年9月20日04:59'}}]}},
            {'para_type': 2, 'pic': {'pics': [{'url': HTTP_IMAGE, 'width': 1920, 'height': 1080}], 'style': 1}},
            {'para_type': 6, 'link_card': {'card': {'common': {'cover': 'https://i0.hdslb.com/bfs/game/unrelated.jpg'}}}},
        ]}},
    ]}}


def test_verified_opus_paragraphs_keep_own_image_and_skip_link_card_cover():
    parsed = opus_content(detail(), UID, '1')
    assert parsed['images'] == [HTTPS_IMAGE]
    for changed in ('author', 'id', 'paywall', 'blocked'):
        raw = detail()
        if changed == 'author': raw['item']['basic']['uid'] = '999'
        elif changed == 'id': raw['item']['id_str'] = '999'
        else: raw['item']['modules'].append({'module_' + changed: { 'message': 'restricted' }})
        with pytest.raises(SourceError): opus_content(raw, UID, '1')


@pytest.mark.parametrize('value', [
    'http://i0.hdslb.com.evil.example/image.jpg',
    'http://i0.hdslb.com@evil.example/image.jpg',
    'https://user:password@i0.hdslb.com/image.jpg',
    'http://i0.hdslb.com:80/image.jpg', 'http://other.example/image.jpg',
    'javascript:alert(1)', 'https://i0.hdslb.com/\nimage.jpg',
])
def test_list_images_reject_unsafe_urls_and_unverified_http_hosts(value):
    item = post('9月15日活动')
    item['modules']['module_dynamic']['major']['opus']['pics'] = [{'url': value}]
    assert classify_dynamic(item, UID, NOW)['images'] == []


async def test_existing_page_request_preserves_list_and_full_images_without_extra_reads(monkeypatch):
    from bilibili_api import opus
    truncated = post('9月15日活动', id='1')
    truncated['modules']['module_dynamic']['major']['opus']['summary']['has_more'] = True
    complete = post('9月15日活动', id='2')
    complete['modules']['module_dynamic']['major']['opus']['pics'] = [{'url': HTTP_IMAGE}]
    calls = []
    async def page(**kwargs):
        calls.append(('page', kwargs))
        return {'items': [deepcopy(truncated), deepcopy(complete)], 'has_more': False}
    class Opus:
        def __init__(self, ident, credential):
            assert ident == 1
        async def get_info(self):
            calls.append(('detail', 1))
            return detail()
    monkeypatch.setattr(opus, 'Opus', Opus)
    client = BilibiliClient.__new__(BilibiliClient)
    client.user, client.uid, client.credential = SimpleNamespace(get_dynamics_new=page), UID, None
    data = await client.page('')
    assert [call[0] for call in calls] == ['page', 'detail']
    rows = [classify_dynamic(item, UID, NOW) for item in data['items']]
    assert [row['images'] for row in rows] == [[HTTPS_IMAGE], [HTTPS_IMAGE]]
    events = parse_post_events(rows[0], 'nte', '1.4')
    assert len(events) == 1 and events[0]['image_urls'] == [HTTPS_IMAGE]
    assert events[0]['source_url'] == rows[0]['url']
    assert events[0]['start_at'] == '2026-09-15T05:00:00+08:00'

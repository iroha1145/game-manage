from copy import deepcopy

import pytest

from game_assistant.accounts.models import AccountScope, QueryResult


def document(game='nte', kind='summary'):
    return dict(version=1, kind=kind, game=game, title='异环 · 账号摘要',
                subtitle='昵称：测试 · UID：123456789',
                sections=[dict(title='账号', fields=[dict(label='等级', value='0'),
                    dict(label='体力', value='未知')], rows=[dict(title='娜娜莉',
                    subtitle='缓存角色', fields=[dict(label='等级', value='80')])])],
                notices=['角色头像使用文字占位'], footer='更新：未知', page=dict(current=1,total=2))


def test_card_text_preserves_zero_unknown_page_and_masks_external_strings():
    from game_assistant.qq.cards import card_to_text, validate_card_document
    card = document()
    card['sections'][0]['rows'][0]['title'] = '<@123>娜\u202e娜莉 https://example.test/a'
    normalized = validate_card_document(card)
    text = card_to_text(normalized)
    assert '等级：0' in text and '体力：未知' in text
    assert '第 1 / 2 页' in text and '更新：未知' in text
    assert '123456789' not in text and 'https:' not in text and '<@' not in text and '\u202e' not in text
    assert card['subtitle'].endswith('123456789')  # caller input is never mutated


@pytest.mark.parametrize('change', [
    lambda c: c.update(asset_url='https://example.test/a'),
    lambda c: c.update(version=True), lambda c: c.update(game='arbitrary'),
    lambda c: c.update(kind=[]),
    lambda c: c['sections'][0]['fields'][0].update(value=0),
    lambda c: c.update(title='x' * 97),
    lambda c: c.update(page=dict(current=3,total=2)),
    lambda c: c.update(sections=[dict(title='x', rows=[dict(title='x')]*13)]),
    lambda c: c.update(sections=[dict(fields=[dict(label='x',value='x'*180)]*12)]*8),
])
def test_card_rejects_unknown_fields_types_and_oversized_content(change):
    from game_assistant.qq.cards import validate_card_document
    card = document()
    change(card)
    with pytest.raises(ValueError):
        validate_card_document(card)


def rendered(card=None, scopes=None, fingerprints=None):
    return QueryResult(dict(card=card or document(), scopes=scopes or [dict(account_id='a', role_id='r', grant_version=1)],
        snapshot_fingerprints=fingerprints or ['a'*64], snapshot_times=[None]), None, 'ok', None)


def test_card_cache_key_follows_every_scope_grant_and_snapshot():
    from game_assistant.qq.rendering import SummaryRenderer
    renderer = SummaryRenderer()
    primary = AccountScope('u','a','r')
    scopes = [dict(account_id='a',role_id='r',grant_version=1),dict(account_id='b',role_id='s',grant_version=1)]
    first = rendered(scopes=scopes)
    changed = deepcopy(scopes); changed[1]['grant_version'] = 2
    assert renderer.cache_key(primary, first) != renderer.cache_key(primary, rendered(scopes=changed))
    assert renderer.cache_key(primary, first) != renderer.cache_key(primary, rendered(scopes=scopes,fingerprints=['b'*64]))


def test_card_scope_and_fingerprint_payload_requires_bounded_types():
    from game_assistant.qq.rendering import RenderingUnavailable, SummaryRenderer
    renderer = SummaryRenderer()
    query = rendered()
    query.payload['scopes'][0]['grant_version'] = True
    with pytest.raises(RenderingUnavailable):
        renderer.cache_key(AccountScope('u','a','r'),query)


def test_card_text_image_mismatch_cannot_enter_cache():
    from game_assistant.qq.rendering import RenderingUnavailable, SummaryRenderer
    query = rendered()
    query.payload['text'] = 'different private snapshot'
    with pytest.raises(RenderingUnavailable):
        SummaryRenderer().cache_key(AccountScope('u','a','r'), query)

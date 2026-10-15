from copy import deepcopy
from io import BytesIO
import socket

from PIL import Image
import pytest

from game_assistant.accounts.models import AccountScope, QueryResult
from tests.qq_test_fonts import cjk_font_path as cjk_font


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


def test_card_render_is_network_free_bounded_and_all_scope_cache_is_revocable(monkeypatch):
    from game_assistant.qq.rendering import SummaryRenderer
    monkeypatch.setattr(socket, 'socket', lambda *a, **k: pytest.fail('renderer attempted network'))
    renderer = SummaryRenderer(font_path=cjk_font())
    primary = AccountScope('u','a','r')
    scopes = [dict(account_id='a',role_id='r',grant_version=1),dict(account_id='b',role_id='s',grant_version=1)]
    first = rendered(scopes=scopes)
    png = renderer.render_summary(primary, first)
    image = Image.open(BytesIO(png))
    assert image.width <= 1080 and image.height <= 2400 and image.width * image.height <= 2592000
    assert len(png) <= renderer.max_bytes
    changed = deepcopy(scopes); changed[1]['grant_version'] = 2
    assert renderer.cache_key(primary, first) != renderer.cache_key(primary, rendered(scopes=changed))
    assert renderer.cache_key(primary, first) != renderer.cache_key(primary, rendered(scopes=scopes,fingerprints=['b'*64]))
    renderer.invalidate_account('u','b')
    assert not renderer.cache


def test_card_invalidation_during_render_does_not_repopulate_cache(monkeypatch):
    from game_assistant.qq import card_rendering
    from game_assistant.qq.rendering import SummaryRenderer
    renderer = SummaryRenderer(font_path=cjk_font())
    original = card_rendering.render_card
    def invalidate(*args, **kwargs):
        renderer.invalidate_account('u','a')
        return original(*args, **kwargs)
    monkeypatch.setattr(card_rendering, 'render_card', invalidate)
    assert renderer.render_summary(AccountScope('u','a','r'), rendered()).startswith(b'\x89PNG')
    assert not renderer.cache


def test_card_render_limits_bytes_pixels_and_missing_font():
    from game_assistant.qq.rendering import RenderingUnavailable, SummaryRenderer
    scope = AccountScope('u','a','r')
    for renderer in (SummaryRenderer(), SummaryRenderer(font_path=cjk_font(),max_bytes=100),
                     SummaryRenderer(font_path=cjk_font(),max_pixels=100)):
        with pytest.raises(RenderingUnavailable):
            renderer.render_summary(scope, rendered())


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


def test_time_budget_fails_before_allocating_image(monkeypatch):
    from game_assistant.qq import card_rendering
    ticks = iter((0, 4))
    monkeypatch.setattr(card_rendering.time,'monotonic',lambda: next(ticks))
    monkeypatch.setattr(card_rendering.Image,'new',lambda *a,**kw: pytest.fail('overspent before allocation'))
    from tests.qq_test_fonts import cjk_font as loaded_font
    with pytest.raises(ValueError, match='time_limit'):
        card_rendering.render_card(document(),font=loaded_font(),budget_seconds=3)


@pytest.mark.parametrize('game,kind', [('all','overview'), ('wuthering_waves','summary'),
    ('nte','summary'), ('endfield','summary'), ('nte','list'), ('endfield','detail'),
    ('all','help'),('all','status')])
def test_shared_templates_preserve_long_names_and_have_finite_mobile_size(game,kind):
    from game_assistant.qq.rendering import SummaryRenderer
    card = document(game,kind)
    card['sections'][0]['rows'][0]['title'] = '这是一个需要自动换行的非常长角色名字用于手机可读性检查' * 2
    png = SummaryRenderer(font_path=cjk_font()).render_summary(AccountScope('u','a','r'),rendered(card))
    image = Image.open(BytesIO(png))
    assert image.height <= 2400 and image.width <= 1080


def test_six_role_page_fits_with_three_cached_fields_per_role():
    from game_assistant.qq.rendering import SummaryRenderer
    card = document('wuthering_waves','list')
    card['sections'][0]['fields'] = []
    card['sections'][0]['rows'] = [dict(title='角色'+str(i), subtitle='本人缓存角色', fields=[
        dict(label='等级',value='90'),dict(label='共鸣链',value='0'),dict(label='武器',value='测试武器名称')]) for i in range(6)]
    png = SummaryRenderer(font_path=cjk_font()).render_summary(AccountScope('u','a','r'), rendered(card))
    assert Image.open(BytesIO(png)).height <= 2400

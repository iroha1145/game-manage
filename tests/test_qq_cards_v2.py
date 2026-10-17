import pytest

from game_assistant.accounts.models import AccountScope, QueryResult
from game_assistant.qq.cards import card_to_text, validate_card_document
from game_assistant.qq.rendering import SummaryRenderer
from tests.qq_test_fonts import cjk_font_path as font

REF = 'qqasset_'+'a'*64


def card(count=40):
    return dict(version=2,kind='list',game='wuthering_waves',title='鸣潮 · 角色档案',
        subtitle='本人默认角色',sections=[dict(title='角色缓存',layout='grid',rows=[
            dict(title='合成测试角色完整长图 '+str(i),image=REF,fields=[dict(label='等级',value='90'),
                dict(label='共鸣链',value='0'),dict(label='属性',value='凝')]) for i in range(count)])],
        notices=['缓存装备不代表完整库存'],footer='更新：2026-10-14 20:30')


class Assets:
    def __init__(self,fingerprint='a'*64):
        self.hash=fingerprint
    def fingerprint(self,ref):
        return self.hash if ref==REF else 'missing'


def test_v2_keeps_sixty_roles_without_page_or_1800_character_truncation():
    normalized=validate_card_document(card(60))
    assert len(normalized['sections'][0]['rows'])==60 and 'page' not in normalized
    text=card_to_text(normalized)
    assert len(text)<=1800 and '文字摘要' in text and '图片或网站' in text
    assert '更新：2026-10-14 20:30' in text and '缓存装备不代表完整库存' in text


@pytest.mark.parametrize('mutate',[
    lambda c:c.update(image='https://untrusted.test/image'),
    lambda c:c['sections'][0].update(layout='html'),
    lambda c:c['sections'][0]['rows'][0].update(image='C:/private/image.png'),
    lambda c:c['sections'][0]['rows'][0]['fields'][0].update(metric=dict(current=True,maximum=10)),
    lambda c:c['sections'][0]['rows'][0]['fields'][0].update(metric=dict(current=0,maximum=float('inf'))),
    lambda c:c['sections'][0]['rows'][0]['fields'][0].update(metric=dict(current=10**1000,maximum=10)),
    lambda c:c.update(sections=[dict(fields=[dict(label='x',value='x')]*48)]*8),
    lambda c:c['sections'][0].update(rows=[dict(title='x')]*257),
])
def test_v2_rejects_urls_paths_bad_metrics_and_document_budgets(mutate):
    value=card(1); mutate(value)
    with pytest.raises(ValueError):validate_card_document(value)


def test_v2_raw_unknown_metric_stays_unknown_and_real_zero_is_accepted():
    value=card(1)
    value['sections'][0]['fields']=[dict(label='体力',value='未知 / 240',metric=dict(current=None,maximum=240)),
        dict(label='探索',value='0 / 100',metric=dict(current=0,maximum=100))]
    fields=validate_card_document(value)['sections'][0]['fields']
    assert fields[0]['metric']['current'] is None and fields[1]['metric']['current']==0


def test_v2_asset_fingerprint_invalidates_visual_cache_when_asset_arrives():
    assets=Assets(fingerprint='missing')
    renderer=SummaryRenderer(font_path=font(),asset_cache=assets)
    result=QueryResult(dict(card=card(1)),None,'ok',None)
    before=renderer.cache_key(AccountScope('u','a','r'),result)
    assets.hash='b'*64
    assert before!=renderer.cache_key(AccountScope('u','a','r'),result)

from io import BytesIO
from pathlib import Path
import socket

from PIL import Image, ImageFont
import pytest

from game_assistant.accounts.models import AccountScope, QueryResult
from game_assistant.qq.cards import card_to_text, validate_card_document
from game_assistant.qq.rendering import SummaryRenderer, RenderingUnavailable

REF = 'qqasset_'+'a'*64


def card(count=40):
    return dict(version=2,kind='list',game='wuthering_waves',title='鸣潮 · 角色档案',
        subtitle='本人默认角色',sections=[dict(title='角色缓存',layout='grid',rows=[
            dict(title='合成测试角色完整长图 '+str(i),image=REF,fields=[dict(label='等级',value='90'),
                dict(label='共鸣链',value='0'),dict(label='属性',value='凝')]) for i in range(count)])],
        notices=['缓存装备不代表完整库存'],footer='更新：2026-10-14 20:30')


def font():
    path=next((p for p in ('C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc') if Path(p).is_file()),None)
    if path is None:pytest.skip('operator CJK font required')
    return path


class Assets:
    def __init__(self,fill='#d5a74f',fingerprint='a'*64):
        self.image=Image.new('RGBA',(192,192),fill)
        self.hash=fingerprint
        self.reads=0
    def get_image(self,ref):
        self.reads+=1
        return self.image.copy() if ref==REF else None
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


def test_v2_grid_uses_cached_images_and_keeps_all_roles_without_network(monkeypatch):
    monkeypatch.setattr(socket,'socket',lambda *a,**kw:pytest.fail('network forbidden'))
    assets=Assets()
    renderer=SummaryRenderer(font_path=font(),asset_cache=assets,max_bytes=1048576)
    png=renderer.render_summary(AccountScope('u','a','r'),QueryResult(dict(card=card(60)),None,'ok',None))
    image=Image.open(BytesIO(png))
    assert image.width==960 and 2400<image.height<=16000 and len(png)<=1048576
    assert assets.reads>0
    colors=image.convert('RGB').getcolors(image.width*image.height)
    assert any(color==(213,167,79) and count>192*192 for count,color in colors)


def test_v2_asset_fingerprint_invalidates_visual_cache_when_asset_arrives():
    assets=Assets(fingerprint='missing')
    renderer=SummaryRenderer(font_path=font(),asset_cache=assets)
    result=QueryResult(dict(card=card(1)),None,'ok',None)
    before=renderer.cache_key(AccountScope('u','a','r'),result)
    assets.hash='b'*64
    assert before!=renderer.cache_key(AccountScope('u','a','r'),result)


def test_v2_pixel_limit_fails_without_partial_image_or_document_truncation():
    value=card(60)
    renderer=SummaryRenderer(font_path=font(),max_pixels=100)
    with pytest.raises(RenderingUnavailable):renderer.render_summary(AccountScope('u','a','r'),QueryResult(dict(card=value),None,'ok',None))
    assert len(value['sections'][0]['rows'])==60


def test_v2_bounded_jpeg_fallback_preserves_readable_dimensions():
    from game_assistant.qq.card_rendering import encode_image
    # Deterministic noisy pixels force PNG above the budget but permit JPEG.
    image=Image.effect_noise((960,2800),35).convert('RGB')
    data=encode_image(image,max_bytes=1048576,check=lambda:None)
    assert data.startswith(b'\xff\xd8') and len(data)<=1048576
    assert Image.open(BytesIO(data)).size==(960,2800)
    with pytest.raises(ValueError):encode_image(image,max_bytes=100,check=lambda:None)


def test_v2_unknown_progress_is_not_drawn_as_a_zero_progress_value():
    from game_assistant.qq.card_rendering import render_card
    value=dict(version=2,game='nte',kind='summary',title='体力',sections=[dict(layout='stats',fields=[
        dict(label='体力',value='未知 / 240',metric=dict(current=None,maximum=240))])])
    unknown=Image.open(BytesIO(render_card(value,font=ImageFont.truetype(font(),30))))
    value['sections'][0]['fields'][0]['metric']['current']=0
    value['sections'][0]['fields'][0]['value']='0 / 240'
    zero=Image.open(BytesIO(render_card(value,font=ImageFont.truetype(font(),30))))
    # Unknown has an interrupted track; known zero has the full neutral track.
    neutral=(48,56,68)
    unknown_track=sum(count for count,pixel in unknown.getcolors(unknown.width*unknown.height) if pixel==neutral)
    zero_track=sum(count for count,pixel in zero.getcolors(zero.width*zero.height) if pixel==neutral)
    assert zero_track-unknown_track>100


@pytest.mark.parametrize('kind',['overview','summary'])
def test_source_metadata_is_compact_and_keeps_minute_timestamp_in_one_drawn_line(kind,monkeypatch):
    from PIL import ImageDraw
    from game_assistant.qq.card_rendering import render_card
    drawn=[]
    original=ImageDraw.ImageDraw.text
    def capture(self,position,value,*args,**kwargs):
        drawn.append((value,kwargs['font'].size))
        return original(self,position,value,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,'text',capture)
    value=dict(version=2,kind=kind,game='nte',title='异环',sections=[dict(title='账号',layout='stats',fields=[
        dict(label='等级',value='42'),dict(label='体力',value='180 / 240'),
        dict(label='更新时间',value='2026-10-14 08:00'),dict(label='体力更新时间',value='2026-10-14 08:01'),
        dict(label='数据状态',value='缓存快照'),dict(label='完整性',value='未知')])])
    png=render_card(value,font=ImageFont.truetype(font(),30))
    assert Image.open(BytesIO(png)).width==960
    level_size=next(size for content,size in drawn if content=='42')
    for stamp in ('2026-10-14 08:00','2026-10-14 08:01'):
        matches=[size for content,size in drawn if stamp in content]
        assert matches and all(size<level_size for size in matches)
    text=card_to_text(value)
    assert '完整性：未知' in text and '数据状态：缓存快照' in text


def test_plain_numeric_stat_does_not_imply_progress_without_a_maximum():
    from game_assistant.qq.card_rendering import render_card
    value=dict(version=2,game='nte',kind='summary',title='账号',sections=[dict(layout='stats',fields=[
        dict(label='等级',value='60',metric=dict(current=60,maximum=None))])])
    with_metric=render_card(value,font=ImageFont.truetype(font(),30))
    del value['sections'][0]['fields'][0]['metric']
    without_metric=render_card(value,font=ImageFont.truetype(font(),30))
    assert with_metric==without_metric

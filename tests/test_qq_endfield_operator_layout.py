"""Operator assembly artwork and facts survive cached/missing icon rendering."""
from copy import deepcopy
from io import BytesIO

from PIL import Image
import pytest

from game_assistant.accounts.models import QueryResult
from game_assistant.qq.assets import PublicAssetCache, sanitize_image
from game_assistant.qq.card_rendering import render_card
from game_assistant.qq.card_rendering_v3 import EndfieldLayout
from game_assistant.qq.cards import card_to_text
from game_assistant.qq.endfield_presentation import operator_document
from game_assistant.qq.presentation import asset_refs, long_document
from tests.test_qq_endfield_reports import cjk_font, snapshot, synthetic_account
from tests.test_qq_unified_queries import no_external_network


@pytest.mark.parametrize('cached',[True,False])
def test_operator_assembly_keeps_real_icon_refs_names_dates_and_unknown_slots(monkeypatch,cached):
    source=synthetic_account();operator=source['operators'][0]
    operator['obtained_at']='2026-01-22T02:51:00Z'
    items=[operator['weapon'],operator['weapon']['gem'],*operator['equipment'],*operator['skills']]
    operator['equipment'].append({'slot':'futureSlot','name':'额外未知槽位装具','level':0,
        'icon_url':'https://web.hycdn.cn/public/extra-equipment.png'})
    items.append(operator['equipment'][-1])
    for index,item in enumerate(items[:-1]):item['icon_url']=f'https://web.hycdn.cn/public/assembly-{index}.png'
    before=deepcopy(source);cache=PublicAssetCache()
    detail=QueryResult(deepcopy(operator),'2026-10-14T00:00:00Z','ok',None)
    card=long_document(operator_document(snapshot(source),'陈千语',cache,detail=detail),asset_cache=cache)
    refs=asset_refs(card)
    item_refs={cache.register_url(item['icon_url']) for item in items}
    assert item_refs<=refs and None not in item_refs
    if cached:
        for index,ref in enumerate(refs):
            marker=BytesIO();size=(303,386) if ref==card['image'] else (120,120)
            Image.new('RGB',size,(30+index*9,130,170)).save(marker,format='PNG')
            cache._store(ref,sanitize_image(marker.getvalue(),portrait=ref==card['image']))
    operations=[];original=EndfieldLayout.paint
    def paint(self,height):operations.extend(self.ops);return original(self,height)
    monkeypatch.setattr(EndfieldLayout,'paint',paint)
    png=render_card(card,font=cjk_font(),asset_cache=cache,max_bytes=524288)
    drawn='\n'.join(operation[2] for operation in operations if operation[0]=='text')
    plain=card_to_text(card)
    for item in items:
        assert item['name'] in drawn and item['name'] in plain
    for value in ('获得时间 2026-01-22 10:51','配装抓取时间 2026-10-14 08:00','槽位 · futureSlot'):
        assert value in drawn
    assert '获得时间：2026-01-22 10:51' in plain and '配装抓取时间：2026-10-14 08:00' in plain
    assert 'Lv.0' in drawn and 'Lv.未知' in drawn
    assert all(operation[3]>=22 for operation in operations if operation[0]=='text')
    images=[operation for operation in operations if operation[0]=='image']
    assert len(images)==(len(items)+1 if cached else 0)
    with Image.open(BytesIO(png)) as picture:
        assert picture.width==1080 and picture.width*picture.height<=16_000_000
    assert len(png)<=524288 and source==before


def test_operator_long_names_keep_all_facts_within_image_transport_budget():
    source=synthetic_account();operator=source['operators'][0]
    operator['weapon']['name']='长武器名称'+('完整名称'*12)
    for index,item in enumerate(operator['equipment']):item['name']=f'装备{index}'+('完整名称'*16)
    card=long_document(operator_document(snapshot(source),'陈千语'))
    png=render_card(card,font=cjk_font(),max_bytes=524288)
    with Image.open(BytesIO(png)) as picture:
        assert picture.width==1080 and picture.width*picture.height<=16_000_000
    assert len(png)<=524288
    for item in [operator['weapon'],*operator['equipment']]:assert item['name'] in card_to_text(card)

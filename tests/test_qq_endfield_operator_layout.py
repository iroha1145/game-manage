"""Operator assembly facts and icon refs survive into the long card and its text."""
from copy import deepcopy

from game_assistant.accounts.models import QueryResult
from game_assistant.qq.assets import PublicAssetCache
from game_assistant.qq.cards import card_to_text
from game_assistant.qq.endfield_presentation import operator_document
from game_assistant.qq.presentation import asset_refs, long_document
from tests.test_qq_endfield_reports import snapshot, synthetic_account
from tests.test_qq_unified_queries import no_external_network


def test_operator_assembly_keeps_real_icon_refs_names_dates_and_unknown_slots():
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
    plain=card_to_text(card)
    for item in items:
        assert item['name'] in plain
    assert '获得时间：2026-01-22 10:51' in plain and '配装抓取时间：2026-10-14 08:00' in plain
    assert source==before


def test_operator_long_names_keep_all_facts_in_text():
    source=synthetic_account();operator=source['operators'][0]
    operator['weapon']['name']='长武器名称'+('完整名称'*12)
    for index,item in enumerate(operator['equipment']):item['name']=f'装备{index}'+('完整名称'*16)
    card=long_document(operator_document(snapshot(source),'陈千语'))
    for item in [operator['weapon'],*operator['equipment']]:assert item['name'] in card_to_text(card)

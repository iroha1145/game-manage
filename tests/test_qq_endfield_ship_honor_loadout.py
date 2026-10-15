"""Observed ship conversion, bounded medal categories and scoped tactical items."""
from copy import deepcopy
from io import BytesIO

from PIL import Image
import pytest

from game_assistant.adapters.endfield.skland_parse import parse_operator
from game_assistant.qq.assets import PublicAssetCache
from game_assistant.qq.card_rendering import render_card
from game_assistant.qq.card_rendering_v3 import EndfieldLayout
from game_assistant.qq.cards import card_to_text
from game_assistant.qq.endfield_presentation import honor_document, operator_document, ship_document
from game_assistant.qq.presentation import long_document
from game_assistant.qq.rendering import TEMPLATE_VERSION
from tests.test_qq_endfield_cached_details import fixture
from tests.test_qq_endfield_reports import cjk_font, snapshot, synthetic_account
from tests.test_qq_endfield_visual_honor import synthetic_honor
from tests.test_qq_unified_queries import CachedQuery, IDENTITY, service, no_external_network


def category_honor(categories=4,each=3):
    source=synthetic_honor(categories*each)
    for index,medal in enumerate(source['achievements']['medals']):
        group=index//each
        medal['achievementData'].update(name=f'合成分类 {group+1} · 勋章 {index%each+1}',
            cateName=f'合成类别 {group+1}' if group else None)
    return source


def test_observed_game_color_spans_are_display_only_without_resolving_parameters():
    from game_assistant.qq.endfield_presentation import _tactical_effect_text
    source = synthetic_account()
    effect = ('每秒回复<@ba.vup>{triggerheal2:0%}</>生命值。'
              '<@tips.purple>支援主控干员</> · <@tips.orange>恢复次数</>；'
              '未知 <foo>原文</foo> 与 {count:0} 保留。')
    source['operators'][0]['tactical_item'] = {
        'name': '合成战术道具', 'active_effect': effect, 'passive_effect': None,
    }
    before = deepcopy(source)
    assert _tactical_effect_text('<@unknown>原文</>') == '<@unknown>原文</>'
    card = operator_document(snapshot(source), '陈千语')
    fields = next(section for section in card['sections']
                  if section.get('category') == 'ef_tactical')['fields']
    prose = ''.join(field['value'] for field in fields if field['label'].startswith('主动效果'))
    assert prose == ('每秒回复{triggerheal2:0%}生命值。支援主控干员 · 恢复次数；'
                     '未知 <foo>原文</foo> 与 {count:0} 保留。')
    assert source == before


@pytest.mark.parametrize('mood,trust,expected_mood,expected_trust,stage',[
    (0,0,'0%','0%','友好'),(6250.129,1064,'62.5%','163%','亲近'),
    (6255,996,'62.6%','158%','亲近'),(10000,1500,'100%','200%','信任'),
    (10001,None,'未知','未知','未知'),(None,300,'未知','100%','亲近')])
def test_ship_percentages_share_rounding_keep_raw_values_and_unknown(mood,trust,expected_mood,expected_trust,stage):
    source=synthetic_account()
    source['ship']=[{'name':'合成舱室','operators':[{'charId':'char_000','physicalStrength':mood,'favorability':trust}]}]
    # Older embedded reports cannot override current conversion from raw facts.
    source['report']={'ship':{'rooms':[{'operators':[{'mood_percent':999}]}]}}
    before=deepcopy(source);card=long_document(ship_document(snapshot(source)))
    row=card['sections'][1]['rows'][0];fields={item['label']:item for item in row['fields']}
    assert fields['心情']['value']==expected_mood and fields['信赖']['value']==expected_trust
    assert fields['信赖阶段']['value']==stage
    assert fields['心情']['metric']['maximum']==100 and fields['信赖']['metric']['maximum']==200
    assert (fields['心情']['metric']['current'] is None)==(expected_mood=='未知')
    assert fields['心情原始值']['value']==('未知' if mood is None else str(mood))
    assert '不按时间外推' in card_to_text(card) and source==before


def test_ship_render_emphasizes_percentages_and_keeps_unknown_track(monkeypatch):
    seen=[];operations=[];original=EndfieldLayout.text;original_paint=EndfieldLayout.paint
    def capture(self,value,x,y,width,size,*args,**kwargs):
        seen.append((value,size));return original(self,value,x,y,width,size,*args,**kwargs)
    monkeypatch.setattr(EndfieldLayout,'text',capture)
    def paint(self,height):
        operations.extend(self.ops);return original_paint(self,height)
    monkeypatch.setattr(EndfieldLayout,'paint',paint)
    card=long_document(ship_document(snapshot()))
    png=render_card(card,font=cjk_font(),max_bytes=524288)
    assert ('85%',36) in seen and ('0%',36) in seen
    assert any('心情原始值 8500' in text and size==22 for text,size in seen)
    assert any(text=='未知' and size==36 for text,size in seen)
    for color in ('#ffd000','#58d5de'):
        assert any(op[0]=='rect' and op[2]==color and op[1][3]-op[1][1]==8 and op[1][2]-op[1][0]>100 for op in operations)
    assert Image.open(BytesIO(png)).width==1080 and len(png)<=524288
    assert TEMPLATE_VERSION=='qq-unified-3-endfield-6'


def assert_honor_counts(card):
    summary=next(section for section in card['sections'] if section.get('category')=='ef_honor_groups')
    grids=[section for section in card['sections'] if section.get('category')=='ef_medals']
    values={field['label']:field['value'] for field in summary['fields']}
    for name,value in values.items():
        shown=int(value.split(' / ')[0])
        matched=[section for section in grids if section['title'].startswith(name+' · ')]
        assert sum(len(section['rows']) for section in matched)==shown
    assert not any('单张长图显示上限' in notice for notice in card['notices'])
    return values


def test_honor_groups_include_unknown_and_do_not_mutate_observations():
    source=category_honor();before=deepcopy(source)
    card=long_document(honor_document(snapshot(source)))
    counts=assert_honor_counts(card)
    assert counts=={'分类未知':'3 / 3','合成类别 2':'3 / 3','合成类别 3':'3 / 3','合成类别 4':'3 / 3'}
    assert source==before and '省略' not in card_to_text(card)


def test_honor_stress_real_query_keeps_all_category_stats_before_fair_details():
    query=CachedQuery();query.add('endfield','skland','sk',{'account':category_honor(8,40)})
    context={};reply=service(query).query(IDENTITY,'honor','endfield',image_context=context)
    card=context['card'];counts=assert_honor_counts(card)
    shown=[int(value.split(' / ')[0]) for value in counts.values()]
    assert len(counts)==8 and len(set(shown))==1 and 0<shown[0]<40
    assert [section['category'] for section in card['sections'][:2]]==['ef_honor','ef_honor_groups']
    for name in counts:assert name in reply['text']
    assert '分类统计优先' in reply['text'] and '省略' in reply['text'] and len(reply['text'])<=1800
    png=render_card(card,font=cjk_font(),max_bytes=524288)
    image=Image.open(BytesIO(png))
    assert image.width*image.height<=16000000 and len(png)<=524288
    assert query.refreshes==[]


def test_honor_excess_categories_have_explicit_coverage():
    card=long_document(honor_document(snapshot(category_honor(20,2))))
    counts=assert_honor_counts(card)
    assert len(counts)==16 and '本图分类 16 / 20' in card_to_text(card)
    assert '超限勋章或分类已省略' in card_to_text(card)


def test_tactical_item_is_consumed_from_only_same_scope_detail_and_fingerprinted(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    cached=scoped._service._operator_cache['c1']['operator']
    cached['tactical_item']=parse_operator({'tacticalItem':{'tacticalItemData':{
        'name':'合成战术道具','rarity':{'value':0},'activeEffect':'恢复 {amount} 点，仅记录原文。',
        'passiveEffect':'合成被动说明','iconUrl':'https://example.invalid/private.png'}}})['tactical_item']
    before=deepcopy(cached);context={}
    reply=service(query).query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=context)
    assert '合成战术道具' in reply['text'] and '稀有度：0' in reply['text'] and '{amount}' in reply['text']
    assert '配装抓取时间：2026-10-14 08:00' in reply['text'] and 'private.png' not in str(context['card'])
    cached['tactical_item']['name']='合成新道具';updated={}
    service(query).query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=updated)
    assert context['fingerprints'][1]!=updated['fingerprints'][1] and cached['weapon']==before['weapon']
    assert query.refreshes==[]


def test_legacy_independent_detail_cannot_relabel_tactical_item_from_account(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    query.data[('sk','account')].payload['operators'][0]['tactical_item']={'name':'档案道具'}
    context={};service(query).query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=context)
    section=next(section for section in context['card']['sections'] if section.get('category')=='ef_tactical')
    assert section['fields']==[{'label':'状态','value':'未采集'}]
    assert '档案道具' not in str(context['card'])


def test_long_tactical_effects_are_measured_and_omissions_are_explicit():
    source=synthetic_account();source['operators'][0]['tactical_item']={
        'name':'合成长名称战术道具 · 用于排版验收','rarity':0,'active_effect':'合成长文效果。'*100,
        'passive_effect':'原始参数 {value} 不进行推算。'}
    card=long_document(operator_document(snapshot(source),'陈千语',PublicAssetCache()))
    section=next(section for section in card['sections'] if section.get('category')=='ef_tactical')
    assert len([field for field in section['fields'] if field['label'].startswith('主动效果')])==4
    assert all(len(field['value'])<=180 for field in section['fields'])
    assert any('过长效果已省略尾部' in notice for notice in card['notices'])
    png=render_card(card,font=cjk_font(),max_bytes=524288)
    assert len(png)<=524288

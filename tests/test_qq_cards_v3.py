from copy import deepcopy
from io import BytesIO
from pathlib import Path
import socket

from PIL import Image, ImageDraw, ImageFont
import pytest

from game_assistant.qq.cards import validate_card_document, card_to_text
from game_assistant.qq.card_rendering import render_card


def font():
    path = next((p for p in ('C:/Windows/Fonts/msyh.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc') if Path(p).is_file()), None)
    if path is None:
        pytest.skip('operator CJK font required')
    return ImageFont.truetype(path, 30)


def calendar():
    return dict(version=3, kind='calendar', game='all', title='合成活动日历',
        timeline=dict(start='2026-10-01', end='2026-11-01', today='2026-10-14', timezone='Asia/Shanghai'),
        sections=[dict(title='鸣潮 · 活动', game='wuthering_waves', category='活动', layout='timeline', rows=[
            dict(title='跨月活动完整长名称', fields=[dict(label='时间',value='2026-09-28 10:00 至 2026-10-21 12:00'),
                dict(label='来源',value='游戏官网 · 合成公告')], timeline=dict(start='2026-09-28',end='2026-10-22',
                precision='minute',continues_before=True,continues_after=False)),
            dict(title='日期待确认',fields=[dict(label='时间',value='版本更新后')])])])


def test_v3_calendar_preserves_axis_precision_and_unknown_boundaries():
    source=calendar()
    normalized=validate_card_document(source)
    assert normalized['timeline']==source['timeline']
    assert 'timeline' not in normalized['sections'][0]['rows'][1]
    assert '版本更新后' in card_to_text(normalized)
    assert source==calendar()


@pytest.mark.parametrize('mutation',[
    lambda c:c['timeline'].update(end='2026-10-01'),
    lambda c:c['timeline'].update(start='2026-02-30'),
    lambda c:c['timeline'].update(timezone='UTC'),
    lambda c:c['sections'][0]['rows'][0]['timeline'].update(precision='unknown'),
    lambda c:c['sections'][0]['rows'][0]['timeline'].update(continues_before=1),
    lambda c:c['sections'][0].update(game='arbitrary'),
])
def test_v3_rejects_unbounded_or_invented_timeline(mutation):
    value=calendar();mutation(value)
    with pytest.raises(ValueError):validate_card_document(value)


def test_v3_help_draws_function_then_command_with_readable_font(monkeypatch):
    drawn=[]
    original=ImageDraw.ImageDraw.text
    def capture(self,position,value,*args,**kwargs):
        drawn.append((position,value,kwargs['font'].size))
        return original(self,position,value,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,'text',capture)
    value=dict(version=3,kind='help',game='all',title='指令帮助',sections=[dict(title='活动',layout='help',fields=[
        dict(label='近期活动',value='鸣潮 近期活动'),dict(label='活动日历',value='日历')])])
    data=render_card(value,font=font())
    assert Image.open(BytesIO(data)).width==1080
    name=next(item for item in drawn if item[1]=='近期活动')
    command=next(item for item in drawn if item[1]=='鸣潮 近期活动')
    assert name[0][1]<command[0][1] and name[2]>=28 and command[2]>=26
    assert min(item[2] for item in drawn)>=22


def test_v3_calendar_draws_shared_axis_today_and_sources_without_network(monkeypatch):
    monkeypatch.setattr(socket,'socket',lambda *a,**k:pytest.fail('render network forbidden'))
    drawn=[]
    original=ImageDraw.ImageDraw.text
    def capture(self,position,value,*args,**kwargs):
        drawn.append(value)
        return original(self,position,value,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,'text',capture)
    data=render_card(calendar(),font=font())
    image=Image.open(BytesIO(data))
    assert image.width==1080 and image.width*image.height<=16_000_000 and len(data)<=1_048_576
    assert any('今天' in text for text in drawn) and any('合成公告' in text for text in drawn)
    assert '日期待确认' in drawn


def gacha():
    return dict(version=3,kind='summary',game='nte',title='全卡池抽卡',sections=[dict(title='角色池',layout='gacha',rows=[
        dict(title='合成角色',fields=[dict(label='获取时间',value='2026-10-14 10:00')],gacha=dict(
            draws=63,guarantee=80,lucky_type=1,color='green',lucky_text='上游评价')),
        dict(title='未知保底',gacha=dict(draws=10,guarantee=None,lucky_type=0,color='yellow',lucky_text=''))])])


def test_v3_gacha_keeps_upstream_colors_and_missing_guarantee_has_no_ratio(monkeypatch):
    from game_assistant.qq import card_rendering_v3
    calls=[]
    original=card_rendering_v3.MobileLayout.gacha_bar
    def capture(self,gacha,*args,**kwargs):
        calls.append(gacha)
        return original(self,gacha,*args,**kwargs)
    monkeypatch.setattr(card_rendering_v3.MobileLayout,'gacha_bar',capture)
    data=render_card(gacha(),font=font())
    colors=Image.open(BytesIO(data)).convert('RGB').getcolors(16_000_000)
    assert any(color==(4,200,163) for count,color in colors)
    assert len(calls)==1 and calls[0]['guarantee']==80


@pytest.mark.parametrize('change',[
    dict(draws=True),dict(guarantee=-1),dict(color='#04c8a3'),dict(lucky_type=0,color='green'),
    dict(lucky_type=0,color='yellow',lucky_text='伪造评价'),dict(draws=10**1000),
])
def test_v3_gacha_rejects_invalid_semantics(change):
    value=gacha();value['sections'][0]['rows'][0]['gacha'].update(change)
    with pytest.raises(ValueError):validate_card_document(value)


def test_v3_long_roles_are_complete_or_explicitly_fail_budget():
    value=dict(version=3,kind='list',game='wuthering_waves',title='合成角色长图',sections=[dict(layout='grid',rows=[
        dict(title='完整角色 '+str(i),subtitle='缓存配装',fields=[dict(label='等级',value='90'),
            dict(label='武器',value='合成武器')]) for i in range(60)])])
    data=render_card(value,font=font())
    image=Image.open(BytesIO(data))
    assert 2400<image.height<=16000 and len(value['sections'][0]['rows'])==60
    with pytest.raises(ValueError,match='pixel_limit'):render_card(value,font=font(),max_pixels=100)


def test_v3_detail_uses_large_portrait_and_calendar_uses_wide_activity_bars(monkeypatch):
    from game_assistant.qq.card_rendering_v3 import MobileLayout
    avatars=[];rectangles=[]
    original_avatar=MobileLayout.avatar;original_rect=MobileLayout.rect
    def avatar(self,ref,title,x,y,width,height,**kwargs):
        avatars.append((width,height))
        return original_avatar(self,ref,title,x,y,width,height,**kwargs)
    def rect(self,coords,*args,**kwargs):
        rectangles.append(coords)
        return original_rect(self,coords,*args,**kwargs)
    monkeypatch.setattr(MobileLayout,'avatar',avatar)
    monkeypatch.setattr(MobileLayout,'rect',rect)
    detail=dict(version=3,kind='detail',game='nte',title='合成角色',sections=[dict(title='角色资料',layout='detail',
        fields=[dict(label='等级',value='80')])])
    render_card(detail,font=font())
    assert any(width>=270 and height>=350 for width,height in avatars)
    render_card(calendar(),font=font())
    assert any(56<=coords[3]-coords[1]<=72 and coords[2]-coords[0]>500 for coords in rectangles)


def test_v3_section_tone_preserves_top_level_upstream_luck_without_row_semantics(monkeypatch):
    value=gacha()
    value['sections'].insert(0,dict(title='社区统计',layout='stats',tone='red',fields=[dict(label='塔吉多近期评价',value='合成上游评价')]))
    assert validate_card_document(value)['sections'][0]['tone']=='red'
    drawn=[];original=ImageDraw.ImageDraw.text
    def capture(self,position,text,*args,**kwargs):
        drawn.append((text,kwargs['fill']));return original(self,position,text,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,'text',capture)
    render_card(value,font=font())
    assert ('合成上游评价','#e55961') in drawn
    value['sections'][0]['tone']='#e55961'
    with pytest.raises(ValueError):validate_card_document(value)


def test_v3_equipment_images_are_validated_rendered_and_participate_in_cache(monkeypatch):
    from game_assistant.qq.cards import image_references
    from game_assistant.qq.card_rendering_v3 import MobileLayout
    ref='qqasset_'+'b'*64
    value=dict(version=3,kind='overview',game='all',title='配装速览',sections=[dict(title='鸣潮',layout='equipment',rows=[
        dict(title='合成角色',equipment=[dict(title='真实采集武器',subtitle='Lv.90',image=ref)])])])
    normalized=validate_card_document(value)
    assert image_references(normalized)==(ref,)
    assert '真实采集武器' in card_to_text(normalized)
    called=[];original=MobileLayout.avatar
    def capture(self,ref,*args,**kwargs):
        called.append(ref);return original(self,ref,*args,**kwargs)
    monkeypatch.setattr(MobileLayout,'avatar',capture)
    render_card(normalized,font=font())
    assert ref in called
    value['sections'][0]['rows'][0]['equipment'][0]['image']='C:/private.png'
    with pytest.raises(ValueError):validate_card_document(value)


def test_v3_overview_equipment_avoids_duplicate_names_and_keeps_counts_and_missing_states():
    from game_assistant.qq.presentation import overview_roles
    from game_assistant.accounts.models import QueryResult
    nte=overview_roles('nte','tajiduo',QueryResult({'entries':[dict(name='合成角色',level=80,weapon=dict(name='已采集弧盘',level=60),
        equipment=[dict(name='已采集装备',slot='槽位',level=25)]),dict(name='缺失角色',level=70)]},None,'ok',None))
    row=nte[0]['rows'][0]
    assert [item['title'] for item in row['equipment']]==['已采集弧盘','已采集装备']
    assert row['fields']==[] and row['subtitle']=='等级 80'
    assert nte[0]['rows'][1]['fields']==[dict(label='装备',value='未采集')]
    ww=overview_roles('wuthering_waves','kuro',QueryResult([dict(role_id=1,name='合成共鸣者',level=90)],None,'ok',None),
        details={'1':{'weapon_data':{'level':90,'weapon':{'weapon_name':'真实武器'}},'phantom_data':{'equip_phantom_list':[
            dict(level=25,phantom_prop={'name':'真实声骸'})]}}})
    assert [item['label'] for item in ww[0]['rows'][0]['fields']]==['已采集声骸']


def test_v3_overview_scope_notice_uses_full_width_metadata_not_stat_tile(monkeypatch):
    from game_assistant.qq.card_rendering_v3 import MobileLayout
    calls=[];original=MobileLayout.field_grid
    def capture(self,fields,*args,**kwargs):
        calls.extend(item['label'] for item in fields)
        return original(self,fields,*args,**kwargs)
    monkeypatch.setattr(MobileLayout,'field_grid',capture)
    value=dict(version=3,kind='overview',game='all',title='总览',sections=[dict(title='角色配装',layout='equipment',fields=[
        dict(label='范围',value='仅已采集配装；完整角色请发送「鸣潮 角色」')],rows=[dict(title='角色')])])
    render_card(value,font=font())
    assert '范围' not in calls

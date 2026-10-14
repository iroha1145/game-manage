import socket

import pytest

from game_assistant.adapters.neverness.assets import parse_realestate, parse_vehicles, parse_teams
from game_assistant.adapters.wuthering_waves.data_models import ActivitiesPayload, ResourcesPayload
from game_assistant.adapters.wuthering_waves.detail_parse import normalize, parse_report
from game_assistant.adapters.wuthering_waves.rolebox import parse_calabash_data


def section_card(section):
    from game_assistant.qq.presentation import long_document, document
    return long_document(document('list','all','专项缓存',sections=[section]))


def section_text(section):
    from game_assistant.qq.cards import card_to_text
    return card_to_text(section_card(section))


def test_calabash_actual_model_preserves_unknown_zero_and_omits_raw_fields():
    from game_assistant.qq.extras import extra_section
    payload = parse_calabash_data(dict(level=0,baseCatch=None,catchQuality=5,curExp=0,maxCount=20)).model_dump()
    payload['token'] = 'sensitive'
    text = section_text(extra_section('wuthering_waves','calabash',payload))
    assert '等级：0' in text and '基础捕获率：未知' in text and '当前经验：0' in text
    assert 'sensitive' not in text and '捕获品质：5' in text and '收集数：20' in text


def test_activities_normalized_source_uses_explicit_fields_and_excludes_scores():
    from game_assistant.qq.extras import extra_section
    payload = ActivitiesPayload(role_id='private',server_id='private',sections=normalize(dict(
        permanentRouge=dict(title='测试玩法',unlock=False,level=0,cardNum=None,maxCardNum=12,
            score=9999,rank='SS',iconUrl='https://assets.test/icon',token='secret')))).model_dump()
    text = section_text(extra_section('wuthering_waves','activities',payload))
    assert '测试玩法' in text and '已解锁：否' in text and '等级：0' in text
    assert '卡牌：未知 / 12' in text
    assert not any(s in text for s in ('9999','SS','https:', 'secret', 'private'))


def test_resources_existing_report_is_period_gain_and_retains_stale_source():
    from game_assistant.qq.extras import extra_section
    report = parse_report(dict(totalCoin=12345678,totalStar=0,starList=[dict(type='每日活动',num=None)],
        coinList=[dict(type='任务',num=0)],itemList=[dict(type='类别',num=0,detail=[dict(type='奖励',num=2)])]))
    payload = ResourcesPayload(role_id='private',server_id='private',periods=dict(month=[dict(period='202609')]),
        current=dict(kind='month',period='202609',data=report,state='stale',fetched_at='2026-09-30T01:00:00Z')).model_dump()
    text = section_text(extra_section('wuthering_waves','resources',payload))
    assert '星声获取：0' in text and '贝币获取：12,345,678' in text
    assert '旧报告' in text and '期间获取量，非钱包余额' in text
    assert '202609' in text and '每日活动' in text and '数量：未知' in text and '奖励' in text
    assert 'private' not in text


def test_nte_assets_actual_models_do_not_infer_unknown_ownership():
    from game_assistant.qq.extras import extra_section
    houses=parse_realestate(dict(detail=[dict(id='1',name='房产测试',own=None,chars=[],fdetail=[dict(id='2',name='椅子',own=0)])],ownCnt=0,total=1)).model_dump()
    vehicles=parse_vehicles(dict(detail=[dict(id='1',name='载具测试',own=True,base=[dict(name='速度',value='0')],advanced=[dict(name='加速',value=None,max='10')])],ownCnt=1,total=None,showName='载具测试')).model_dump()
    h=section_text(extra_section('nte','realestate',houses)); v=section_text(extra_section('nte','vehicles',vehicles))
    assert '已拥有：0' in h and '拥有状态：未知' in h and '椅子' in h and '拥有状态：否' in h
    assert '总数：未知' in v and '拥有状态：是' in v and '速度：0' in v and '加速：未知 / 10' in v


def test_official_teams_are_source_text_only_and_never_fetch_assets(monkeypatch):
    from game_assistant.qq.extras import extra_section
    monkeypatch.setattr(socket,'socket',lambda *a,**k: pytest.fail('network forbidden'))
    payload=parse_teams([dict(id='1',name='官方组合测试',desc='官方来源的已有说明',icon='https://assets.test/i',imgs=['https://assets.test/x'])]).model_dump()
    text=section_text(extra_section('nte','teams',payload))
    assert '官方组合测试' in text and '官方来源的已有说明' in text and '官方缓存' in text
    assert 'assets.test' not in text and 'https:' not in text


@pytest.mark.parametrize('game,cap',[('wuthering_waves','calabash'),('wuthering_waves','activities'),
    ('wuthering_waves','resources'),('nte','realestate'),('nte','vehicles'),('nte','teams')])
def test_extras_none_is_unknown_not_zero(game,cap):
    from game_assistant.qq.extras import extra_section
    text=section_text(extra_section(game,cap,None))
    assert '未知' in text or '暂无' in text
    assert '：0' not in text


def test_long_official_team_document_keeps_all_rows_and_text_is_explicit_summary():
    from game_assistant.qq.cards import card_to_text
    from game_assistant.qq.extras import extra_section
    section=extra_section('nte','teams',dict(entries=[
        dict(name='角色'+str(i)+'名字'*80,description={'token':'secret'}) for i in range(40)]))
    card=section_card(section)
    assert 'page' not in card
    rows=card['sections'][0]['rows']
    assert len(rows)==40
    assert rows[0]['title'].startswith('角色0') and rows[-1]['title'].startswith('角色39')
    assert all(len(row['title'])<=72 for row in rows)
    text=card_to_text(card)
    assert len(text)<=1800 and '文字摘要' in text and '完整内容见图片或网站' in text
    assert '40 个缓存条目' in text and 'secret' not in text


def test_unmatched_game_capability_returns_none():
    from game_assistant.qq.extras import extra_section
    assert extra_section('endfield','vehicles',{}) is None

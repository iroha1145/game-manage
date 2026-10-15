"""Calendar uses official NOTICE feed, not the default promotional INFO feed."""
import httpx
import pytest
import respx

from game_assistant.adapters.neverness.adapter import NteAdapter
from game_assistant.adapters.neverness.tajiduo_client import TajiduoWebClient
from game_assistant.config import Settings
from game_assistant.models import Capability
from tests.adapters.test_nte_adapter import COMMUNITY_RAW, EVENTS_POST_FULL_RAW

BASE='https://bbs-api.tajiduo.com'
LIST=BASE+'/bbs/wapi/getOfficialPostList'
DETAIL=BASE+'/bbs/wapi/getPostFull'
INFO={'code':0,'data':{'posts':[{'postId':511836,'subject':'拾光切片丨黑羽','createTime':1791561600000}],
                      'page':0,'hasMore':True}}
# Public headline structure from the 2026-10-13 NOTICE-filter probe; bodies below are synthetic.
NOTICES={'code':0,'data':{'page':0,'hasMore':True,'posts':[
    {'postId':438597,'subject':'《异环》1.3版本「雾中朔望星回」更新公告','createTime':1786507200000},
    {'postId':494294,'subject':'《异环》1.4版本「祷歌为谁而诵」更新公告','createTime':1790139834502},
    {'postId':600001,'subject':'《异环》1.5版本前瞻特别资讯','createTime':1791741600000},
    {'postId':476642,'subject':'停服维护公告','createTime':1791655200000},
]}}
NOTICE_BODY=('<p>● 全新限定S级角色「测试角色」</p>'
    '<p>开放时间：9月24日版本更新后-10月15日05:59</p>'
    '<p>● 「环期赠礼」签到活动</p><p>活动时间：9月24日版本更新后-11月5日05:59</p>'
    '<p>● 「像素溢出」限时活动</p><p>活动时间：10月12日05:00-10月19日04:59</p>')


@respx.mock
async def test_explicit_notice_filter_uses_numeric_type_and_version_without_changing_default_feed():
    route=respx.get(LIST).respond(200,json=NOTICES)
    async with TajiduoWebClient() as web:
        await web.get_official_post_list('4',count=20,official_type=3)
        await web.get_official_post_list('4',count=20)
    first,second=[call.request for call in route.calls]
    assert dict(first.url.params)=={'columnId':'4','count':'20','officialType':'3','version':'0'}
    assert dict(second.url.params)=={'columnId':'4','count':'20'}
    assert 'authorization' not in first.headers and 'ds' not in first.headers


@respx.mock
async def test_named_version_notice_is_selected_without_promotional_feed_or_bulk_detail_reads():
    respx.get(BASE+'/apihub/wapi/getAllCommunity').respond(200,json=COMMUNITY_RAW)
    def response(request):
        return httpx.Response(200,json=NOTICES if request.url.params.get('officialType')=='3' else INFO)
    listing=respx.get(LIST).mock(side_effect=response)
    detail=respx.get(DETAIL,params={'postId':'494294'}).respond(200,json={
        **EVENTS_POST_FULL_RAW,'data':{'post':{**EVENTS_POST_FULL_RAW['data']['post'],
            'postId':494294,'subject':'《异环》1.4版本「祷歌为谁而诵」更新公告',
            'content':EVENTS_POST_FULL_RAW['data']['post']['content'].replace('1.5', '1.4')}}})
    result=await NteAdapter(Settings()).fetch(Capability.EVENTS)
    assert result.ok and result.payload
    assert {event.source_post_id for event in result.payload}=={'494294'}
    assert {event.source_title for event in result.payload}=={'《异环》1.4版本「祷歌为谁而诵」更新公告'}
    assert listing.call_count==1 and detail.call_count==1
    assert result.payload[1].start_at is None


@respx.mock
async def test_absent_version_notice_has_finite_budget_and_remains_failure():
    respx.get(BASE+'/apihub/wapi/getAllCommunity').respond(200,json=COMMUNITY_RAW)
    listing=respx.get(LIST).respond(200,json=INFO)
    result=await NteAdapter(Settings()).fetch(Capability.EVENTS)
    assert not result.ok and result.error_kind=='source_error' and result.payload is None
    assert listing.call_count==1
    assert len(respx.calls)==2  # community + bounded 20-row NOTICE list, no fabricated pagination/details.


@respx.mock
async def test_news_preserves_default_official_information_feed():
    respx.get(BASE+'/apihub/wapi/getAllCommunity').respond(200,json=COMMUNITY_RAW)
    listing=respx.get(LIST).respond(200,json=INFO)
    result=await NteAdapter(Settings()).fetch(Capability.ANNOUNCEMENT)
    assert result.ok and result.payload[0].title=='拾光切片丨黑羽'
    assert dict(listing.calls[0].request.url.params)=={'columnId':'4','count':'20'}


@respx.mock
async def test_notice_format_preserves_relative_start_and_verified_publication_year():
    respx.get(BASE+'/apihub/wapi/getAllCommunity').respond(200,json=COMMUNITY_RAW)
    respx.get(LIST).respond(200,json=NOTICES)
    respx.get(DETAIL).respond(200,json={'code':0,'data':{'post':{
        'postId':494294,'subject':NOTICES['data']['posts'][1]['subject'],
        'createTime':1790139834502,'content':NOTICE_BODY}}})
    result=await NteAdapter(Settings()).fetch(Capability.EVENTS)
    assert result.ok and [event.name for event in result.payload]==['测试角色','环期赠礼','像素溢出']
    first,_,pixel=result.payload
    assert first.start_at is None and first.start_date=='2026-09-24'
    assert first.start_precision=='relative' and first.start_text=='9月24日版本更新后'
    assert first.end_at.isoformat()=='2026-10-15T05:59:00+08:00'
    assert first.source=='community' and first.source_name=='塔吉多官方公告' and first.version=='1.4'
    assert first.source_post_id=='494294' and first.time_text
    assert first.model_dump()['start_at'] is None and first.model_dump()['start_date']=='2026-09-24'
    assert pixel.start_at.isoformat()=='2026-10-12T05:00:00+08:00' and pixel.start_precision=='minute'
    assert pixel.end_at.isoformat()=='2026-10-19T04:59:00+08:00'


@respx.mock
async def test_short_calendar_dates_without_publication_year_remain_failure():
    respx.get(BASE+'/apihub/wapi/getAllCommunity').respond(200,json=COMMUNITY_RAW)
    post={'postId':494294,'subject':NOTICES['data']['posts'][1]['subject']}
    respx.get(LIST).respond(200,json={'code':0,'data':{'posts':[post]}})
    respx.get(DETAIL).respond(200,json={'code':0,'data':{'post':{**post,'content':NOTICE_BODY}}})
    result=await NteAdapter(Settings()).fetch(Capability.EVENTS)
    assert not result.ok and result.error_kind=='invalid_data' and result.payload is None


@respx.mock
async def test_same_version_independent_notice_adds_pool_and_keeps_version_precision():
    respx.get(BASE+'/apihub/wapi/getAllCommunity').respond(200,json=COMMUNITY_RAW)
    card={'postId':700001,'subject':'1.4版本「独立棋盘」限定棋盘开放','createTime':1791741600000}
    other={**card,'postId':700002,'subject':'1.5版本「其它棋盘」限定棋盘开放'}
    respx.get(LIST).respond(200,json={'code':0,'data':{'posts':[*NOTICES['data']['posts'],card,other]}})
    def response(request):
        ident=request.url.params['postId']
        if ident=='494294':
            row={**NOTICES['data']['posts'][1],'content':NOTICE_BODY}
        elif ident=='700001':
            row={**card,'content':'<p>活动期间概率限时提升！</p><p>开放时间</p><p>10月12日05:00-11月5日05:59</p>'}
        else:
            raise AssertionError('unrelated version detail must not be requested')
        return httpx.Response(200,json={'code':0,'data':{'post':row}})
    detail=respx.get(DETAIL).mock(side_effect=response)
    result=await NteAdapter(Settings()).fetch(Capability.EVENTS)
    assert result.ok and len(result.payload)==4
    event=next(e for e in result.payload if e.name=='独立棋盘')
    assert event.source_post_id=='700001' and event.version=='1.4' and event.source=='community'
    assert event.start_at.isoformat()=='2026-10-12T05:00:00+08:00'
    assert detail.call_count==2


@respx.mock
async def test_selected_independent_notice_failure_does_not_publish_partial_calendar():
    respx.get(BASE+'/apihub/wapi/getAllCommunity').respond(200,json=COMMUNITY_RAW)
    card={'postId':700001,'subject':'1.4版本「独立棋盘」限定棋盘开放','createTime':1791741600000}
    respx.get(LIST).respond(200,json={'code':0,'data':{'posts':[*NOTICES['data']['posts'],card]}})
    respx.get(DETAIL,params={'postId':'494294'}).respond(200,json={'code':0,'data':{'post':{
        **NOTICES['data']['posts'][1],'content':NOTICE_BODY}}})
    respx.get(DETAIL,params={'postId':'700001'}).respond(503)
    result=await NteAdapter(Settings()).fetch(Capability.EVENTS)
    assert not result.ok and result.error_kind=='source_error' and result.payload is None


@pytest.mark.parametrize('title,body', [
    ('「其它棋盘」限定棋盘开放', '1.5版本「其它棋盘」限定棋盘\n开放时间：10月12日05:00-11月5日05:59'),
    ('「其它棋盘」限定棋盘开放', '「其它棋盘」限定棋盘\n开放时间：12月12日05:00-12月15日05:59'),
    ('1.4版本「其它棋盘」限定棋盘开放', '1.5版本「其它棋盘」限定棋盘\n开放时间：10月12日05:00-11月5日05:59'),
])
@respx.mock
async def test_independent_notice_requires_consistent_version_or_matching_dates(title, body):
    respx.get(BASE+'/apihub/wapi/getAllCommunity').respond(200,json=COMMUNITY_RAW)
    card={'postId':700001,'subject':title,'createTime':1791741600000}
    respx.get(LIST).respond(200,json={'code':0,'data':{'posts':[*NOTICES['data']['posts'],card]}})
    respx.get(DETAIL,params={'postId':'494294'}).respond(200,json={'code':0,'data':{'post':{
        **NOTICES['data']['posts'][1],'content':NOTICE_BODY}}})
    respx.get(DETAIL,params={'postId':'700001'}).respond(200,json={'code':0,'data':{'post':{**card,'content':body}}})
    result=await NteAdapter(Settings()).fetch(Capability.EVENTS)
    assert result.ok and len(result.payload)==3
    assert all(e.name!='其它棋盘' for e in result.payload)


@respx.mock
async def test_independent_notice_reads_have_finite_budget():
    respx.get(BASE+'/apihub/wapi/getAllCommunity').respond(200,json=COMMUNITY_RAW)
    cards=[{'postId':700000+i,'subject':'1.4版本「独立棋盘」限定棋盘开放','createTime':1791741600000} for i in range(20)]
    respx.get(LIST).respond(200,json={'code':0,'data':{'posts':[NOTICES['data']['posts'][1],*cards]}})
    def response(request):
        ident=request.url.params['postId']
        row=NOTICES['data']['posts'][1] if ident=='494294' else next(c for c in cards if str(c['postId'])==ident)
        content=NOTICE_BODY if ident=='494294' else '开放时间：10月12日05:00-11月5日05:59'
        return httpx.Response(200,json={'code':0,'data':{'post':{**row,'content':content}}})
    detail=respx.get(DETAIL).mock(side_effect=response)
    result=await NteAdapter(Settings()).fetch(Capability.EVENTS)
    assert result.ok and len(result.payload)==4
    assert detail.call_count==7

from dataclasses import asdict
from types import SimpleNamespace

import pytest

from game_assistant.qq.commands import parse_command, safe_text
from game_assistant.qq.models import QqIdentity
from game_assistant.qq.query_routes import QqQueryService
from game_assistant.accounts.models import QueryResult
from game_assistant.identity.models import Principal
from game_assistant.qq.bindings import QqBindingError

IDENTITY = QqIdentity('app','group','group','sender')


def test_commands_are_explicit_self_queries():
    for raw,command,game in [('/help','help',None),('绑定 CODE','binding',None),
                            ('我的账号','status',None),('/ww','summary','wuthering_waves'),
                            ('/yh','summary','nte'),('/endfield','summary','endfield'),
                            ('鸣潮角色','roles','wuthering_waves'),('活动 鸣潮','events','wuthering_waves'),
                            ('公告 异环','news','nte'),('刷新 终末地','refresh','endfield'),('看板','dashboard',None)]:
        parsed=parse_command(raw)
        assert parsed.command==command and parsed.game==game
    for raw in ['/ww other-account','异环 123456789','刷新 异环 其他用户','/help https://secret.example']:
        assert parse_command(raw).command=='help'


@pytest.mark.parametrize('raw,command,game',[
    ('ww 查询','summary','wuthering_waves'),('yh 查询','summary','nte'),
    ('终末地 查询','summary','endfield'),('/ww 活动','events','wuthering_waves'),
    ('ww 公告','news','wuthering_waves'),('yh 刷新','refresh','nte'),
    ('ww 角色','roles','wuthering_waves'),
])
def test_game_first_command_aliases_remain_self_only(raw,command,game):
    parsed = parse_command(raw)
    assert parsed.command == command and parsed.game == game
    if command == 'roles':
        assert parse_command(raw+' own-role').role_name == 'own-role'
        assert parse_command(raw+' own-role other-user').command == 'help'
    else:
        assert parse_command(raw+' other-user').command == 'help'


@pytest.mark.parametrize('raw',['ww 角色 今汐','/鸣潮 角色 长离','wuthering_waves roles Shorekeeper'])
def test_named_role_filter_targets_own_cached_exact_name(raw):
    from game_assistant.qq.cards import card_to_text
    from game_assistant.qq.presentation import help_document
    parsed = parse_command(raw)
    assert parsed.command == 'roles' and parsed.game == 'wuthering_waves'
    assert parsed.role_name == raw.split()[-1]
    assert '鸣潮 角色 精确名称' in card_to_text(help_document('wuthering_waves'))


def test_named_role_filter_is_bounded_printable_and_roles_only():
    assert parse_command('ww 角色 '+'名'*64).role_name == '名'*64
    for raw in ('ww 角色 '+'名'*65,'ww 角色 名\x00字','ww 角色 名\x1f字','ww 角色 今汐 other-user',
                'ww 查询 今汐','ww 公告 今汐'):
        parsed = parse_command(raw)
        assert parsed.command == 'help' and parsed.role_name is None
    assert parse_command('ww 角色').role_name is None


def test_url_removed_when_not_approved():
    assert 'example' not in safe_text('网址 https://example.com/a 与 www.example.com、example.com',urls_approved=False)
    assert 'https://example.com' in safe_text('https://example.com',urls_approved=True)


def test_reply_masks_uid_preserves_null_and_failed_cache():
    import json
    from tests.test_qq_unified_queries import CachedQuery, service
    query=CachedQuery();query.add('nte','tajiduo','n',{})
    query.data[('n','account')]=QueryResult({'nickname':'User 123456789','level':None,'extra':{'uid':'123456789','token':'private-secret'}},'2026-10-12T00:00:00Z','error',False)
    context={};text=service(query).query(IDENTITY,'summary','nte',image_context=context)['text']
    assert '123456789' not in text and 'private-secret' not in text
    assert '等级：未知' in text and '显示旧快照' in text and '完整性：不完整' in text
    projected=json.dumps(context['render_snapshot'],ensure_ascii=False)
    assert '123456789' not in projected and 'private-secret' not in projected


def unbound_service():
    def resolve(identity):
        raise QqBindingError('qq_link_required',403)
    return QqQueryService(SimpleNamespace(resolve_qq_identity=resolve),None,None)


def test_unbound_user_gets_help_only():
    service=unbound_service()
    assert '帮助' in service.query(IDENTITY,'help')['text']
    assert '绑定' in service.query(IDENTITY,'summary','nte')['text']
    assert '绑定' in service.query(IDENTITY,'status')['text']


def test_public_queries_do_not_require_bound_game():
    service=unbound_service()
    service.public=SimpleNamespace(read=lambda game,cap:QueryResult([{'title':'Public notice','url':'https://example.com'}],None,'never',None))
    assert 'Public notice' in service.query(IDENTITY,'news','nte')['text']
    assert 'https://' not in service.query(IDENTITY,'news','nte')['text']


async def test_web_and_qq_share_snapshot(tmp_path):
    from tests.test_account_queries import query_fixture
    accounts,scope,store,query=await query_fixture(tmp_path)
    store.save_scoped(scope,'account','{"nickname":"Same player","level":17}',1)
    service=QqQueryService(SimpleNamespace(resolve_qq_identity=lambda identity:Principal('a',False)),query,None)
    website=query.read(scope,'account')
    assert 'Same player' in service.query(IDENTITY,'summary','nte')['text']
    assert str(website.payload['level']) in service.query(IDENTITY,'summary','nte')['text']
    accounts.revoke(Principal('a',False),scope.account_id)
    assert 'Same player' not in service.query(IDENTITY,'summary','nte')['text']


def test_self_query_cannot_target_other_account(tmp_path):
    from tests.test_qq_internal_auth import client
    from game_assistant.cloud_app import create_cloud_app
    from game_assistant.config import Settings
    app=create_cloud_app(Settings(cloud_db_path=str(tmp_path/'cloud.db'),cloud_allowed_origins=['https://cloud.example'],qq_app_id='app',qq_service_token='fixture-secret'),start_scheduler=False)
    c=client(app)
    body={'identity':asdict(IDENTITY),'command':'help'}
    assert c.post('/internal/qq/query',json=body).status_code==401
    auth={'Authorization':'Bearer fixture-secret'}
    assert c.post('/internal/qq/query',json=body,headers=auth).status_code==200
    for key in ('user_id','account_id','role_id'):
        response=c.post('/internal/qq/query',json={**body,key:'other-private-value'},headers=auth)
        assert response.status_code==422 and 'other-private-value' not in response.text
    response=c.post('/internal/qq/query',json={**body,'identity':{**asdict(IDENTITY),'app_id':'other'}},headers=auth)
    assert response.status_code==400


def test_endfield_providers_choose_default_separately():
    rows=[dict(account_id='h2',game='endfield',provider='hypergryph',state='active',is_default=0,roles=[dict(role_id='r',is_default=1)]),
          dict(account_id='s',game='endfield',provider='skland',state='active',is_default=0,roles=[dict(role_id='r',is_default=1)]),
          dict(account_id='h1',game='endfield',provider='hypergryph',state='active',is_default=1,roles=[dict(role_id='r',is_default=1)])]
    reads=[]
    class Query:
        accounts=SimpleNamespace(require_scope=lambda p,a,r:SimpleNamespace(user_id=p.user_id,account_id=a,role_id=r))
        def list_accounts(self,p):return rows
        def capabilities(self,scope):return ['account']
        def read(self,scope,cap):
            reads.append(scope.account_id)
            return QueryResult({'nickname':scope.account_id},None,'never',None)
    service=QqQueryService(SimpleNamespace(resolve_qq_identity=lambda i:Principal('a',False)),Query(),None)
    text=service.query(IDENTITY,'summary','endfield')['text']
    assert reads==['h1','s'] and '鹰角寻访' in text and '森空岛' in text


def test_skland_reply_has_name_level_stamina_without_role_id():
    import json
    from tests.test_qq_unified_queries import CachedQuery, service
    query=CachedQuery()
    query.add('endfield','skland','sk',{'account':{'base':{'name':'Operator','level':24,'role_id':'sensitive-role'},
                                                    'stamina':{'current':None,'maximum':200}}})
    context={};text=service(query).query(IDENTITY,'summary','endfield',image_context=context)['text']
    assert 'Operator' in text and '账号等级：24' in text and '未知/200' in text
    assert 'sensitive-role' not in text and 'sensitive-role' not in json.dumps(context['render_snapshot'],ensure_ascii=False)


async def test_internal_binding_redeems_once_with_trusted_message_id():
    from datetime import datetime,timezone,timedelta
    import httpx
    from game_assistant.qq.client import InternalQqClient
    from game_assistant.qq.models import InboundMessage
    requests=[]
    def respond(request):
        requests.append(request)
        return httpx.Response(200,json={'status':'linked','link_id':'fixture-link'})
    http=httpx.AsyncClient(transport=httpx.MockTransport(respond))
    client=InternalQqClient('http://127.0.0.1:8000','secret',http=http)
    now=datetime.now(timezone.utc)
    message=InboundMessage(IDENTITY,'msg','绑定 CODE',now.isoformat(),(now+timedelta(minutes=5)).isoformat())
    text=await client.execute(message)
    assert '绑定成功' in text and 'CODE' not in text and '填回' not in text
    assert requests[0].url.path=='/internal/qq/link-redemptions'
    import json
    assert json.loads(requests[0].content)['message_id']=='msg'
    assert requests[0].headers['authorization']=='Bearer secret'
    await http.aclose()


def test_internal_client_rejects_remote_or_redirect_endpoint():
    from game_assistant.qq.client import InternalQqClient,QqClientError
    for url in ('https://example.com','http://localhost:8000','http://127.0.0.1@evil.example','http://127.0.0.1/x'):
        with pytest.raises(QqClientError):InternalQqClient(url,'fixture-secret')


def test_unapproved_dashboard_has_no_url_and_approved_dashboard_works():
    service=unbound_service()
    service.dashboard_url='https://dashboard.example.com'
    assert 'example' not in service.query(IDENTITY,'dashboard')['text']
    service.urls_approved=True
    assert service.query(IDENTITY,'dashboard')['text']=='https://dashboard.example.com'


async def test_internal_remote_failure_does_not_echo_details():
    import httpx
    from game_assistant.qq.client import InternalQqClient,QqClientError
    http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503,json={'detail':'private-token'})))
    client=InternalQqClient('http://127.0.0.1:8000','fixture-secret',http=http)
    with pytest.raises(QqClientError) as error:await client.post('/internal/qq/query',{})
    assert 'private-token' not in str(error.value)
    await http.aclose()


async def test_loopback_client_sends_explicit_host_for_actual_cloud_boundary(tmp_path):
    import httpx
    from game_assistant.qq.client import InternalQqClient
    from game_assistant.cloud_app import create_cloud_app
    from game_assistant.config import Settings
    app=create_cloud_app(Settings(cloud_db_path=str(tmp_path/'cloud.db'),
        cloud_allowed_origins=['https://dashboard.example'],qq_app_id='app',qq_service_token='fixture-secret'),start_scheduler=False)
    http=httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('127.0.0.1',1234)))
    client=InternalQqClient('http://127.0.0.1:8020','fixture-secret',internal_host='dashboard.example',http=http)
    result=await client.post('/internal/qq/query',{'identity':asdict(IDENTITY),'command':'help'})
    assert '帮助' in result['text']
    await http.aclose()


def test_domains_written_right_after_chinese_text_are_masked():
    from game_assistant.qq.commands import safe_text
    assert safe_text('官网kurogames.com领取') == '官网[链接未启用]领取'
    assert safe_text('详见 www.kurogames.com。') == '详见 [链接未启用]'
    # An email address still keeps its domain; only standalone domains are links.
    assert safe_text('邮箱 a@kurogames.com') == '邮箱 a@kurogames.com'


@pytest.mark.parametrize('alias,command',[
    ('日历','calendar'),('calendar','calendar'),('活动','events'),('events','events'),
    ('近期活动','recent_events'),('recent_events','recent_events'),
])
@pytest.mark.parametrize('page',[1,2,100])
def test_public_cross_game_page_commands(alias,command,page):
    parsed=parse_command(f'/{alias} {page}')
    assert (parsed.command,parsed.game,parsed.page)==(command,None,page)
    assert parsed.role_name is None and parsed.code is None


@pytest.mark.parametrize('raw',[
    '日历 0','活动 101','近期活动 -1','日历 +2','日历 2.0','日历 ２',
    '日历 2 other-user','活动 other-user 2','近期活动 2 3',
    '绑定 CODE 2','看板 2','体力 2','刷新 2',
    '终末地 刷新 2',
])
def test_page_syntax_keeps_invalid_and_unpaged_commands_rejected(raw):
    parsed=parse_command(raw)
    assert parsed.command=='help' and parsed.page==1 and parsed.code is None


@pytest.mark.parametrize('alias,command',[
    ('总览','overview'),('我的总览','overview'),('overview','overview'),
    ('状态','status'),('我的账号','status'),('status','status'),
])
def test_overview_and_status_existing_continuations_keep_their_meaning(alias,command):
    assert parse_command(f'{alias} 2').command==command
    assert parse_command(f'{alias} 2').page==2
    assert parse_command(f'{alias} 101').command=='help'


def test_snapshot_next_commands_parse_back_into_their_public_or_scoped_query():
    from datetime import datetime
    from game_assistant.qq.render_snapshot import (
        calendar_snapshot, filtered_events_snapshot, game_snapshot, role_snapshot, gacha_snapshot,
    )
    now=datetime.fromisoformat('2026-10-17T12:00:00+08:00')
    empty=QueryResult([],now.isoformat(),'ok',True)
    rows={game:empty for game in ('wuthering_waves','nte','endfield')}
    snapshots=[(calendar_snapshot(rows,now),'calendar',None,None)]
    for command in ('events','recent_events'):
        snapshots.append((filtered_events_snapshot(rows,command,now),command,None,None))
    for game,label in (('wuthering_waves','鸣潮'),('nte','异环'),('endfield','终末地')):
        snapshots.append((calendar_snapshot({game:empty},now),'calendar',game,None))
        snapshots.append((game_snapshot([],now,command=label+' 总览'),'summary',game,None))
    nte=QueryResult({'schema_version':1,'entries':[{'id':'9001','name':'合成角色','level':0}]},now.isoformat(),'ok',True)
    wuwa=QueryResult({'role':{'role_name':'合成角色','level':0}},now.isoformat(),'ok',True)
    snapshots.extend([
        (role_snapshot('nte',nte,now),'roles','nte',None),
        (role_snapshot('nte',nte,now,resolved_id='9001'),'roles','nte','9001'),
        (role_snapshot('wuthering_waves',wuwa,now,detail=wuwa,resolved_id='1501'),'roles','wuthering_waves','1501'),
        (gacha_snapshot('wuthering_waves',empty,now),'gacha','wuthering_waves',None),
        (gacha_snapshot('nte',empty,now),'gacha','nte',None),
        (game_snapshot([],now,command='终末地 寻访战报'),'gacha','endfield',None),
    ])
    for snapshot,command,game,role in snapshots:
        continuation=snapshot['next_command']+' 2'
        parsed=parse_command(continuation)
        assert (parsed.command,parsed.game,parsed.page,parsed.role_name)==(command,game,2,role),continuation


@pytest.mark.parametrize('raw,command,game',[
    ('帮助 2','help',None),('help 100','help',None),('鸣潮 帮助 2','help','wuthering_waves'),
    ('异环 体力 2','stamina','nte'),('鸣潮 数据坞 2','calabash','wuthering_waves'),
    ('终末地 理智 2','stamina','endfield'),
])
def test_read_only_queries_can_continue_without_enabling_action_pagination(raw,command,game):
    from game_assistant.qq.query_routes import QueryBody
    parsed=parse_command(raw)
    assert (parsed.command,parsed.game)==(command,game) and parsed.page>=2
    body=QueryBody(identity=asdict(IDENTITY),command=parsed.command,game=parsed.game,page=parsed.page)
    assert body.page==parsed.page
    assert parse_command(raw.rsplit(' ',1)[0]+' 101').command=='help'


@pytest.mark.parametrize('command',['refresh','dashboard'])
def test_action_query_bodies_still_reject_pagination(command):
    from game_assistant.qq.query_routes import QueryBody
    with pytest.raises(ValueError,match='page_not_supported'):
        QueryBody(identity=asdict(IDENTITY),command=command,game='nte',page=2)


@pytest.mark.parametrize('command,game,role',[
    ('help',None,None),('help','nte',None),('status',None,None),('overview',None,None),
    ('summary','nte',None),('stamina','nte',None),('calabash','wuthering_waves',None),
    ('exploration','nte',None),('combat','nte',None),('progress','nte',None),
    ('activities','nte',None),('resources','nte',None),('realestate','nte',None),
    ('vehicles','nte',None),('teams','nte',None),('record','nte',None),
    ('news','nte',None),('gacha','nte',None),
    ('roles','wuthering_waves',None),
    ('roles','endfield','陈千语'),('training','endfield',None),
    ('calendar','nte',None),('events','nte',None),('recent_events','nte',None),
    ('events',None,None),('recent_events',None,None),('calendar',None,None),
])
def test_query_snapshot_continuation_preserves_the_query(command,game,role):
    from tests.test_qq_unified_queries import CachedQuery,service
    query=CachedQuery()
    query.add('nte','tajiduo','n',{'account':{'nickname':'测试'},'stamina':{'current':0}})
    query.add('wuthering_waves','kuro','w',{'roles':[{'role_id':'1','name':'今汐','level':0}]})
    query.add('endfield','skland','e',{'account':{'operators':[{'id':'1','name':'陈千语','level':0}]}})
    api=service(query)
    api.public=SimpleNamespace(read=lambda *args:QueryResult([],None,'ok',True))
    context={}
    api.query(IDENTITY,command,game,role_name=role,image_context=context)
    snapshot=context['render_snapshot']
    parsed=parse_command(snapshot['next_command']+' 2')
    assert (parsed.command,parsed.game,parsed.role_name,parsed.page)==(command,game,role,2),snapshot['next_command']


async def test_multipage_action_reply_falls_back_without_exposing_action_continuation():
    from game_assistant.qq.rendering import RenderedImage
    from tests.test_qq_unified_queries import CachedQuery,service
    query=CachedQuery();query.add('nte','tajiduo','n',{'stamina':{'current':0}})
    class Queue:
        renderer=SimpleNamespace(invalidate_account=lambda *args:None)
        async def render(self,scope,result,**kwargs):return RenderedImage(b'png',page=1,total_pages=2)
    api=service(query);api.render_queue=Queue()
    reply=await api.query_reply(IDENTITY,'refresh','nte',image_requested=True,budget_seconds=5)
    assert 'image' not in reply and '图片暂不可用' in reply['text'] and '下一页' not in reply['text']
    assert len(query.refreshes)==1 and query.refreshes[0][1]=='stamina'

"""QQ consumes only web-observed, same-scope Skland operator details."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from game_assistant.accounts.models import AccountScope
from game_assistant.adapters.endfield.skland_client import SklandError
from game_assistant.endfield_skland import EndfieldSklandService
from game_assistant.private_routes import PrivateRoutes
from tests.test_qq_unified_queries import CachedQuery, IDENTITY, service, no_external_network


def forbidden(*args,**kwargs):
    raise AssertionError('Cached QQ detail attempted credential loading or upstream I/O')


def detail(operator_id='c1',**changes):
    value={'operator':{'id':operator_id,'name':'佩丽卡','level':999,
            'weapon':{'name':'已观测详情武器','level':80,'refine_level':0},
            'equipment':[{'slot':'bodyEquip','name':'已观测详情护甲','level':70}],
            'skills':[{'name':'已观测详情战技','level':9}]},
           'fetched_at':'2026-10-14T00:00:00Z','stale':False,'error':None}
    value.update(changes)
    return value


def fixture(tmp_path, *, cached=True):
    query=CachedQuery()
    scope=query.add('endfield','skland','sk',{'account':{'base':{'name':'本人档案'},
        'operators':[{'id':'c1','name':'佩丽卡','level':70,'potential':0,'weapon':None,'equipment':[],'skills':[]}]}})
    grant={'id':'grant-sk','provider':'skland'}
    original=query.describe
    query.accounts.describe=lambda checked:{**original(checked),'game':'endfield','provider':grant['provider'],'grant_id':grant['id']}
    query.accounts.credentials=SimpleNamespace(load_grant=forbidden)
    bundle=PrivateRoutes(query.accounts,None,tmp_path/'never-created')
    query.private=bundle
    # Creating these in-memory objects is fixture setup, never a query action.
    scoped=EndfieldSklandService.for_scope(scope,dict(cred='synthetic',user_id='source-user',role_id='source-role',server_id='1'),
        client=SimpleNamespace(refresh=forbidden,operator=forbidden))
    if cached:
        scoped._service._operator_cache['c1']=detail()
        bundle._skland[scope]=(1,grant['id'],scoped)
    bundle.skland=forbidden
    return query,scope,grant,bundle,scoped


def test_scoped_cache_getter_is_a_deep_copy_and_refuses_other_scopes(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    result=bundle.cached_skland_operator(scope,'c1')
    result['operator']['weapon']['name']='mutated'
    assert scoped.cached_operator(scope,'c1')['operator']['weapon']['name']=='已观测详情武器'
    for other in (AccountScope('other',scope.account_id,scope.role_id),
                  AccountScope(scope.user_id,'other',scope.role_id),AccountScope(scope.user_id,scope.account_id,'other')):
        assert bundle.cached_skland_operator(other,'c1') is None
        with pytest.raises(PermissionError):scoped.cached_operator(other,'c1')
    assert scoped.cached_operator(scope,'missing') is None
    assert scoped.cached_operator(scope,'../c1') is None
    assert not bundle.private_root.exists()


@pytest.mark.parametrize('change',['version','grant','provider'])
def test_old_grant_or_provider_cache_is_not_adopted(tmp_path,change):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    if change=='version':query.versions['sk']=2
    elif change=='grant':grant['id']='replacement-grant'
    else:grant['provider']='hypergryph'
    assert bundle.cached_skland_operator(scope,'c1') is None
    assert scoped._service._operator_cache['c1']['operator']['id']=='c1'


def test_getter_rechecks_grant_after_copy_and_closed_services_ignore_late_result(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    original=scoped.cached_operator
    def changed(checked,char_id):
        result=original(checked,char_id);grant['id']='rotated-during-read';return result
    scoped.cached_operator=changed
    assert bundle.cached_skland_operator(scope,'c1') is None
    scoped.cached_operator=original
    scoped.close();scoped._service._operator_cache['c1']=detail()
    assert scoped.cached_operator(scope,'c1') is None


def test_missing_detail_never_constructs_service_reads_credentials_or_refreshes(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path,cached=False)
    assert bundle.cached_skland_operator(scope,'c1') is None
    text=service(query).query(IDENTITY,'roles','endfield',role_name='佩丽卡')['text']
    assert '未找到独立详情缓存' in text and '已观测详情武器' not in text
    assert bundle._skland=={} and query.refreshes==[] and not bundle.private_root.exists()


def test_same_id_detail_keeps_newer_basic_stats_and_separate_observation_time(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    # The account cache is newer than the independent operator observation.
    previous=query.data[('sk','account')]
    query.data[('sk','account')]=type(previous)(previous.payload,'2026-10-14T01:00:00Z','ok',None)
    context={};text=service(query).query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=context)['text']
    assert '已观测详情武器' in text and '已观测详情护甲' in text and '已观测详情战技' in text
    assert '等级：70' in text and '999' not in text
    assert '配装抓取时间：2026-10-14 08:00' in text and '档案抓取时间：2026-10-14 09:00' in text
    assert '早于当前档案' in text and len(context['snapshots'])==2
    assert context['snapshots'][1].fetched_at=='2026-10-14T00:00:00Z'
    assert len(context['grants'])==1 and query.refreshes==[]
    assert query.data[('sk','account')].payload['operators'][0]['weapon'] is None


def test_mismatched_detail_id_is_rejected_and_duplicate_names_do_not_read_cache(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    scoped._service._operator_cache['c1']=detail('foreign-id')
    context={};text=service(query).query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=context)['text']
    assert '已观测详情武器' not in text and len(context['snapshots'])==1
    query.data[('sk','account')].payload['operators'].append({'id':'c2','name':'佩丽卡'})
    bundle.cached_skland_operator=forbidden
    assert '同名角色' in service(query).query(IDENTITY,'roles','endfield',role_name='佩丽卡')['text']


def test_changed_detail_and_failure_state_participate_in_image_cache_fingerprint(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    api=service(query);first={};second={};failed={}
    api.query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=first)
    scoped._service._operator_cache['c1']['operator']['weapon']['level']=81
    api.query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=second)
    assert first['fingerprints'][0]==second['fingerprints'][0]
    assert first['fingerprints'][1]!=second['fingerprints'][1]
    scoped._service._operator_cache['c1'].update(stale=True,error='NEVER_EXPOSE_RAW_ERROR')
    response=api.query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=failed)
    assert second['fingerprints'][1]!=failed['fingerprints'][1]
    assert '最近读取失败，显示旧详情' in response['text'] and 'NEVER_EXPOSE_RAW_ERROR' not in response['text']
    assert failed['snapshots'][1].fetched_at=='2026-10-14T00:00:00Z'


async def test_failed_web_read_persists_staleness_without_retimestamping_success(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    inner=scoped._service;calls=[];moment=datetime(2026,10,14,tzinfo=timezone.utc)
    inner.clock=lambda:moment
    async def refresh(*args):calls.append('refresh');return 'mock-signature'
    async def operator(*args):calls.append('operator');return {'id':'c1','charData':{'name':'佩丽卡'},'level':80}
    inner.client=SimpleNamespace(refresh=refresh,operator=operator)
    fresh=await scoped.read_operator(scope,'c1')
    moment+=timedelta(hours=2)
    async def failed(*args):calls.append('operator');raise SklandError('synthetic upstream failure')
    inner.client.operator=failed
    old=await scoped.read_operator(scope,'c1');before=list(calls)
    cached=bundle.cached_skland_operator(scope,'c1')
    assert cached['stale'] and cached['fetched_at']==fresh['fetched_at']==old['fetched_at']
    assert calls==before
    scoped._service._operator_cache.clear()
    await scoped.read_operator(scope,'c1')
    response=service(query).query(IDENTITY,'roles','endfield',role_name='佩丽卡')
    assert '最近读取失败，未取得独立详情' in response['text']


@pytest.mark.parametrize('change',['version','grant'])
async def test_grant_change_during_operator_image_render_suppresses_private_reply(tmp_path,change):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    class Queue:
        renderer=SimpleNamespace(invalidate_account=lambda *args:None)
        async def render(self,scope,result,**kwargs):
            assert len(result.payload['snapshot_fingerprints'])==2
            if change=='version':query.versions['sk']+=1
            else:grant['id']='replacement-with-same-version'
            return b'image'
    response=await service(query,queue=Queue()).query_reply(IDENTITY,'roles','endfield',role_name='佩丽卡',
        image_requested=True,budget_seconds=5)
    assert 'image' not in response and '变更' in response['text'] and '佩丽卡' not in response['text']


def test_replaced_grant_identity_changes_fingerprint_even_with_same_version_and_payload(tmp_path):
    query,scope,grant,bundle,scoped=fixture(tmp_path)
    api=service(query);first={};second={}
    api.query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=first)
    grant['id']='replacement-with-same-version'
    bundle._skland[scope]=(1,grant['id'],scoped)
    api.query(IDENTITY,'roles','endfield',role_name='佩丽卡',image_context=second)
    assert len(first['fingerprints'])==len(second['fingerprints'])==2
    assert all(a!=b for a,b in zip(first['fingerprints'],second['fingerprints']))

"""Challenge cards reuse only default, same-grant website observations."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from game_assistant.accounts.models import AccountScope
from game_assistant.adapters.endfield.skland_client import SklandError
from game_assistant.endfield_challenges import build_challenge_report
from game_assistant.qq.commands import parse_command
from game_assistant.qq.presentation import long_document
from tests.test_qq_endfield_cached_details import fixture, forbidden
from tests.test_qq_unified_queries import IDENTITY, service, no_external_network


def synthetic_challenges():
    group={'name':'合成关卡组','star':0,
           'normalDungeon':{'name':'普通试炼','isPass':True},
           'hardDungeon':{'name':'困难试炼','isPass':False},
           'cruelDungeon':{'name':'险境试炼','isPass':None}}
    war={'supported':True,'kind':'war','fetched_at':'2026-10-14T01:30:00Z','stale':False,'error':None,
         'records':[{'id':'s1','name':'合成赛季','stars':0,'start_at':None,'end_at':None,
                     'weeks':[{'id':'w1','name':'第一周','stars':0,'groups':[group]}]}],
         'summary':{'honors':[{'name':'合成荣誉','star':0,'first_pass_at':None}]}}
    monument={'supported':True,'kind':'monument','fetched_at':'2026-10-14T02:30:00Z','stale':True,
              'error':'RAW_ERROR_MUST_NOT_LEAK','records':[{'id':'m1','name':'合成丰碑','groups':[deepcopy(group)]}],
              'summary':{'count':1}}
    crisis={'supported':True,'kind':'crisis','fetched_at':'2026-10-14T03:30:00Z','stale':False,'error':None,
            'records':[{'id':'r1','score':0,'isPass':False},{'id':'r2','grade':None}],
            'summary':{'highest':0,'challenge_count':None}}
    return {'war':war,'monument':monument,'crisis':crisis}


def setup(tmp_path, *, cached=True):
    query,scope,grant,bundle,scoped=fixture(tmp_path,cached=cached)
    if cached:
        scoped._service._challenge_cache.update({(kind,None,None,None):value for kind,value in synthetic_challenges().items()})
    # Metadata-only selection must bypass every credential-resolving query API.
    query.list_accounts=query.capabilities=query.adapter=query.read=forbidden
    return query,scope,grant,bundle,scoped


def test_default_queries_only_scoped_deepcopy_and_no_credentials(tmp_path):
    query,scope,grant,bundle,scoped=setup(tmp_path)
    result=bundle.cached_skland_challenge(scope,'war')
    result['records'][0]['name']='changed'
    assert scoped.cached_challenge(scope,'war')['records'][0]['name']=='合成赛季'
    for other in (AccountScope('other',scope.account_id,scope.role_id),
                  AccountScope(scope.user_id,'other',scope.role_id),AccountScope(scope.user_id,scope.account_id,'other')):
        assert bundle.cached_skland_challenge(other,'war') is None
        with pytest.raises(PermissionError):scoped.cached_challenge(other,'war')
    assert scoped.cached_challenge(scope,'unverified') is None
    del scoped._service._challenge_cache[('war',None,None,None)]
    scoped._service._challenge_cache[('war','s1',None,None)]=synthetic_challenges()['war']
    assert bundle.cached_skland_challenge(scope,'war') is None
    scoped._service._challenge_cache[('war',None,None,None)]=synthetic_challenges()['crisis']
    assert bundle.cached_skland_challenge(scope,'war') is None
    assert not bundle.private_root.exists()


@pytest.mark.parametrize('change',['version','grant','provider'])
def test_changed_grants_never_adopt_old_challenges(tmp_path,change):
    query,scope,grant,bundle,scoped=setup(tmp_path)
    if change=='version':query.versions['sk']=2
    elif change=='grant':grant['id']='replacement'
    else:grant['provider']='hypergryph'
    assert bundle.cached_skland_challenge(scope,'war') is None


@pytest.mark.parametrize('change',['grant','instance'])
def test_getter_double_checks_grant_and_instance_and_refuses_late_result(tmp_path,change):
    query,scope,grant,bundle,scoped=setup(tmp_path)
    original=scoped.cached_challenge
    def changed(checked,kind):
        result=original(checked,kind)
        if change=='grant':grant['id']='rotated-during-read'
        else:bundle._skland.pop(scope)
        return result
    scoped.cached_challenge=changed
    assert bundle.cached_skland_challenge(scope,'war') is None
    scoped.cached_challenge=original;scoped.close()
    scoped._service._challenge_cache[('war',None,None,None)]=synthetic_challenges()['war']
    assert scoped.cached_challenge(scope,'war') is None


def test_qq_challenge_keeps_zero_unknown_separate_times_and_only_default_provider(tmp_path):
    query,scope,grant,bundle,scoped=setup(tmp_path)
    query.add('endfield','hypergryph','hg',{})
    other=query.add('endfield','skland','other',{},default=False)
    context={};reply=service(query).query(IDENTITY,'combat','endfield',image_context=context)
    text=reply['text']
    assert '合成赛季' in text and '合成丰碑' in text and '最高值：0' in text
    assert '挑战次数：未知' in text and '记录结果：0' in text and '通关状态：未知' in text
    assert '普通 · 普通试炼：已通关' in text and '困难 · 困难试炼：未通关' in text
    assert '险境 · 险境试炼：未知' in text and '赛季星数：0' in text
    for moment in ('09:30','10:30','11:30'):assert '2026-10-14 '+moment in text
    assert '显示旧观测' in text and 'RAW_ERROR_MUST_NOT_LEAK' not in text
    assert context['grants']==[(scope,1)] and len(context['snapshots'])==3
    assert [s.state for s in context['snapshots']]==['ok','error','ok']
    assert all(s.complete is None for s in context['snapshots'])
    assert query.reads==query.refreshes==[] and other not in bundle._skland


def test_missing_cache_does_not_construct_service_or_claim_empty_history(tmp_path):
    query,scope,grant,bundle,scoped=setup(tmp_path,cached=False)
    context={};text=service(query).query(IDENTITY,'combat','endfield',image_context=context)['text']
    assert text.count('尚未采集；请在网站查看此挑战分类')==3
    assert '已采集记录：0' not in text and text.count('已采集记录：未知')==3
    assert all(s.fetched_at is None for s in context['snapshots'])
    assert bundle._skland=={} and not bundle.private_root.exists() and query.refreshes==[]


def test_real_account_query_does_not_resolve_runtime_or_load_snapshot(tmp_path):
    from game_assistant.accounts.query import AccountQuery
    query,scope,grant,bundle,scoped=setup(tmp_path)
    real=AccountQuery(query.accounts,SimpleNamespace(for_scope=forbidden),
                      SimpleNamespace(get_scoped=forbidden),private=bundle)
    text=service(real).query(IDENTITY,'combat','endfield')['text']
    assert '合成赛季' in text and '最高值：0' in text


def test_hypergryph_only_cannot_supply_challenge_records(tmp_path):
    query,scope,grant,bundle,scoped=setup(tmp_path)
    query.rows[0]['provider']='hypergryph'
    bundle.cached_skland_challenge=forbidden
    assert '挑战需要本人森空岛档案授权' in service(query).query(IDENTITY,'combat','endfield')['text']


def test_projection_is_allowlisted_nonmutating_and_does_not_infer_empty_progress():
    value=synthetic_challenges()['crisis']
    value['summary']['best_record']={'secret':'DO_NOT_PROJECT'}
    value['records'][0].update(cred='DO_NOT_PROJECT',chars=[{'secret':'DO_NOT_PROJECT'}])
    before=deepcopy(value);report=build_challenge_report(value)
    assert 'DO_NOT_PROJECT' not in str(report) and value==before
    assert report['summary']['highest']==0 and report['summary']['challenge_count'] is None
    empty=build_challenge_report({**value,'records':[]})
    assert empty['available'] and empty['summary']['listed_count']==0
    unknown=build_challenge_report({**value,'fetched_at':None,'stale':True})
    assert not unknown['available'] and unknown['summary']['listed_count'] is None and unknown['records']==[]
    mismatch=build_challenge_report(value,kind='war')
    assert not mismatch['available'] and mismatch['records']==[]
    malformed=build_challenge_report({**value,'records':[{'id':float('nan'),'score':float('inf'),'isPass':1}]})
    assert malformed['records'][0]['id'] is None and malformed['records'][0]['result'] is None
    assert malformed['records'][0]['passed'] is None


def test_changed_content_or_failure_changes_independent_image_fingerprint(tmp_path):
    query,scope,grant,bundle,scoped=setup(tmp_path)
    api=service(query);first={};second={};third={}
    api.query(IDENTITY,'combat','endfield',image_context=first)
    scoped._service._challenge_cache[('crisis',None,None,None)]['summary']['highest']=10
    api.query(IDENTITY,'combat','endfield',image_context=second)
    assert first['fingerprints'][:2]==second['fingerprints'][:2]
    assert first['fingerprints'][2]!=second['fingerprints'][2]
    scoped._service._challenge_cache[('crisis',None,None,None)]['stale']=True
    api.query(IDENTITY,'combat','endfield',image_context=third)
    assert second['fingerprints'][2]!=third['fingerprints'][2]
    assert second['snapshots'][2].fetched_at==third['snapshots'][2].fetched_at


async def test_web_failure_is_persisted_with_original_success_time(tmp_path):
    query,scope,grant,bundle,scoped=setup(tmp_path)
    inner=scoped._service;calls=[];moment=datetime(2026,10,14,tzinfo=timezone.utc)
    inner.clock=lambda:moment
    async def refresh(*args):calls.append('refresh');return 'synthetic-token'
    async def challenge(*args,**kwargs):calls.append('challenge');return {'seasons':[{'id':'s1','stars':0}]}
    inner.client=SimpleNamespace(refresh=refresh,challenge=challenge)
    fresh=await scoped.read_challenges(scope,'war')
    assert fresh['report']['summary']['listed_count']==1 and fresh['report']['stale'] is False
    moment+=timedelta(hours=2)
    async def failed(*args,**kwargs):calls.append('challenge');raise SklandError('RAW_ERROR_MUST_NOT_LEAK')
    inner.client.challenge=failed
    old=await scoped.read_challenges(scope,'war');before=list(calls)
    cached=bundle.cached_skland_challenge(scope,'war')
    assert cached['stale'] and cached['fetched_at']==fresh['fetched_at']==old['fetched_at']
    assert cached['report']['stale'] and cached['report']['fetched_at']==fresh['fetched_at']
    assert calls==before
    inner._challenge_cache.clear()
    await scoped.read_challenges(scope,'war')
    text=service(query).query(IDENTITY,'combat','endfield')['text']
    assert '最近读取失败，尚无成功观测' in text and 'RAW_ERROR_MUST_NOT_LEAK' not in text


@pytest.mark.parametrize('change',['version','grant'])
async def test_grant_change_during_image_render_suppresses_challenge_reply(tmp_path,change):
    query,scope,grant,bundle,scoped=setup(tmp_path)
    class Queue:
        renderer=SimpleNamespace(invalidate_account=lambda *args:None)
        async def render(self,scope,result,**kwargs):
            assert len(result.payload['snapshot_fingerprints'])==3
            if change=='version':query.versions['sk']+=1
            else:grant['id']='replacement-with-same-version'
            return b'image'
    reply=await service(query,queue=Queue()).query_reply(IDENTITY,'combat','endfield',image_requested=True,budget_seconds=5)
    assert 'image' not in reply and '变更' in reply['text'] and '合成赛季' not in reply['text']


def test_challenge_command_and_long_card_are_bounded(tmp_path):
    assert parse_command('终末地 挑战').command=='combat'
    query,scope,grant,bundle,scoped=setup(tmp_path)
    context={};service(query).query(IDENTITY,'combat','endfield',image_context=context)
    huge=deepcopy(context['card']);huge['sections']*=100
    assert any('省略' in notice for notice in long_document(huge)['notices'])

"""Public forum collection must not consume private game credentials."""
import json
import re
from urllib.parse import parse_qs

import pytest
import respx

from game_assistant.accounts.query import CloudPublicQuery, AccountQuery
from game_assistant.accounts.runtime import AccountRuntime
from game_assistant.accounts.store import AccountNotFoundError
from game_assistant.adapters.wuthering_waves.adapter import WutheringWavesAdapter
from game_assistant.auth.service import LoginService
from game_assistant.auth.store import CredentialStore
from game_assistant.config import Settings
from game_assistant.models import Capability, FetchResult
from game_assistant.registry import GameRegistry
from game_assistant.snapshots import SnapshotStore
from game_assistant.identity.models import Principal
from tests.test_account_auth import setup

LIST = 'https://api.kurobbs.com/forum/companyEvent/findEventList'
DETAIL = 'https://api.kurobbs.com/forum/getPostDetail'
PUBLIC = (Capability.ANNOUNCEMENT, Capability.EVENTS)
LIST_DATA = {'code':200,'data':{'list':[{'postId':'9001','postTitle':'3.6版本内容说明'}]}}
DETAIL_DATA = {'code':200,'data':{'postDetail':{'postId':'9001','postTitle':'3.6版本内容说明',
    'postH5Content':'<p>[合成活动]战斗活动</p><p>活动时间：版本更新后 ~ 2026年10月30日11:59（服务器时间）</p>'}}}


@pytest.mark.parametrize('capability', PUBLIC)
@pytest.mark.parametrize('configured', [False, True])
@respx.mock
async def test_public_forum_request_works_without_credentials_and_never_uses_private_headers(capability, configured):
    respx.post(LIST).respond(200,json=LIST_DATA)
    respx.post(DETAIL).respond(200,json=DETAIL_DATA)
    settings = Settings(wuwa_token='private-token',wuwa_user_id='private-user',wuwa_did='private-device',
                        wuwa_b_at='private-ticket',wuwa_dev_code='private-device-code') if configured else Settings()
    adapter = WutheringWavesAdapter(settings)
    result = await adapter.fetch(capability)
    assert result.ok and len(result.payload)==1
    for call in respx.calls:
        assert not set(call.request.headers) & {'token','authorization','b-at','did'}
        assert re.fullmatch(r'[0-9a-f]{32}',call.request.headers.get('devcode',''))
        assert 'private-' not in str(call.request.headers)
    assert len({call.request.headers['devcode'] for call in respx.calls})==1
    assert parse_qs(respx.calls[0].request.content.decode()) == {'gameId':['3'],'eventType':['3']}
    assert parse_qs(respx.calls[1].request.content.decode()) == {'postId':['9001'],'isOnlyPublisher':['0'],'showOrderType':['2']}
    if capability == Capability.ANNOUNCEMENT:
        assert result.payload[0].published_at is None
    else:
        assert result.payload[0].start_at is None
        assert result.payload[0].end_at.isoformat() == '2026-10-30T11:59:00+08:00'
        assert result.payload[0].source_post_id=='9001'


@pytest.mark.parametrize('capability', PUBLIC)
@respx.mock
async def test_anonymous_public_rejection_is_source_error_without_auth_expiry(capability):
    respx.post(LIST).respond(403,json={'code':403,'msg':'untrusted upstream original'})
    result = await WutheringWavesAdapter(Settings()).fetch(capability)
    assert not result.ok and result.error_kind=='source_error' and result.error_code==403
    assert 'upstream original' not in result.error


@respx.mock
async def test_public_detail_rejection_keeps_listing_and_marks_body_unavailable():
    respx.post(LIST).respond(200,json=LIST_DATA)
    respx.post(DETAIL).respond(403,json={'msg':'untrusted upstream original'})
    result=await WutheringWavesAdapter(Settings()).fetch(Capability.ANNOUNCEMENT)
    assert result.ok and result.payload[0].title=='3.6版本内容说明'
    assert result.payload[0].content_status=='error'
    assert 'upstream original' not in result.payload[0].content_error


@pytest.mark.parametrize('returned_id,expected', [('9001',True),('wrong',False)])
@respx.mock
async def test_public_detail_supports_official_id_and_rejects_wrong_source(returned_id,expected):
    respx.post(LIST).respond(200,json=LIST_DATA)
    respx.post(DETAIL).respond(200,json={'code':200,'data':{'postDetail':{
        'id':returned_id,'postH5Content':DETAIL_DATA['data']['postDetail']['postH5Content']}}})
    result=await WutheringWavesAdapter(Settings()).fetch(Capability.ANNOUNCEMENT)
    assert result.ok
    assert (result.payload[0].content_status=='full') is expected


@pytest.mark.parametrize('capability', PUBLIC)
async def test_local_auth_does_not_renew_or_mark_private_login_expired_for_public_failure(tmp_path, capability):
    settings = Settings(wuwa_token='private-token',wuwa_user_id='private-user',wuwa_role_id='private-role')
    service = LoginService(settings,CredentialStore(tmp_path/'unused'))
    result = FetchResult(ok=False,error='Public unavailable',error_code=403,error_kind='source_error')
    async def rejected():return result
    assert await service.fetch('wuthering_waves',capability,rejected) is result
    assert not service._errors
    assert settings.wuwa_token=='private-token'


def public_query(store):
    registry=GameRegistry()
    registry.register(WutheringWavesAdapter(Settings()))
    return CloudPublicQuery(registry,store)


def test_first_announcement_failure_propagates_to_news_without_fabricating_snapshot():
    store=SnapshotStore(':memory:')
    store.record_poll('wuthering_waves','announcement',FetchResult(ok=False,error_kind='source_error'))
    result=public_query(store).read('wuthering_waves','news')
    assert result.state=='error' and result.payload is None and result.fetched_at is None
    assert store.get('wuthering_waves','announcement') is None


def test_announcement_failure_preserves_previous_news_payload_and_timestamp():
    store=SnapshotStore(':memory:')
    store.save('wuthering_waves','announcement',json.dumps([{'id':'old','title':'Saved announcement','published_at':None}]))
    fetched_at=store.get('wuthering_waves','announcement')['fetched_at']
    store.record_poll('wuthering_waves','announcement',FetchResult(ok=False,error_kind='source_error'))
    result=public_query(store).read('wuthering_waves','news')
    assert result.state=='error' and result.fetched_at==fetched_at
    assert result.payload[0]['title']=='Saved announcement' and result.payload[0]['published_at'] is None


@respx.mock
async def test_cloud_public_poll_attempts_anonymous_forum_and_retains_failed_old_snapshots():
    respx.post(LIST).respond(403)
    store=SnapshotStore(':memory:')
    store.save('wuthering_waves','events','[{"name":"Saved event","start_at":null,"end_at":null}]')
    old=store.get('wuthering_waves','events')
    query=public_query(store)
    await query.poll('wuthering_waves')
    assert query.read('wuthering_waves','news').state=='error'
    assert query.read('wuthering_waves','events').state=='error'
    assert store.get('wuthering_waves','events')==old
    assert store.get('wuthering_waves','announcement') is None


def test_scoped_private_query_still_excludes_public_forum_capabilities(tmp_path):
    _,_,accounts,_=setup(tmp_path)
    principal=Principal('a',False)
    saved=accounts.save_verified(principal,'kuro',{'user_id':'synthetic-user','role_id':'synthetic-role',
        'server_id':'synthetic-server','token':'synthetic-token'})
    scope=accounts.require_scope(principal,saved['account_id'],saved['role_id'])
    runtime=AccountRuntime(accounts,Settings(),tmp_path/'runtime')
    query=AccountQuery(accounts,runtime,SnapshotStore(':memory:'))
    assert 'account' in query.capabilities(scope)
    for capability in ('announcement','events','news'):
        with pytest.raises(AccountNotFoundError):query.read(scope,capability)

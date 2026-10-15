"""Bounded public-only DoH uses fixed verified HTTPS and has no fallback."""
from copy import deepcopy
import asyncio
import json
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from game_assistant.qq import public_asset_dns as dns
from game_assistant.qq import assets

HOST='bbs.hycdn.cn'

def answer():
    return {'Status':0,'TC':False,'CD':False,'Question':[{'name':HOST,'type':1}],
            'Answer':[{'name':HOST,'type':5,'TTL':30,'data':'cdn.example.net.'},
                      {'name':'cdn.example.net.','type':1,'TTL':30,'data':'1.1.1.1'}]}

def test_doh_public_cname_chain_and_exact_endpoint_addresses():
    rows=dns._addresses(json.dumps(answer()),HOST)
    assert rows==[(socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',('1.1.1.1',443))]

@pytest.mark.parametrize('address',['127.0.0.1','10.0.0.1','192.168.0.1','169.254.1.1','198.18.0.1','0.0.0.0','224.0.0.1','::1','::ffff:10.0.0.1'])
def test_doh_refuses_every_nonpublic_or_non_a_answer(address):
    value=answer();value['Answer'][-1]['data']=address
    with pytest.raises(ValueError):dns._addresses(json.dumps(value),HOST)

@pytest.mark.parametrize('change',['question','status','truncated','checking_disabled','loop','unrelated','bad_owner','too_many'])
def test_doh_rejects_mismatched_or_unbounded_dns_envelopes(change):
    value=answer()
    if change=='question':value['Question'][0]['name']='evil.example'
    elif change=='status':value['Status']=True
    elif change=='truncated':value['TC']=True
    elif change=='checking_disabled':value['CD']=True
    elif change=='loop':value['Answer'][0]['data']=HOST
    elif change=='unrelated':value['Answer'].append({'name':'other.example','type':5,'TTL':1,'data':'cdn.example.net'})
    elif change=='bad_owner':value['Answer'][-1]['name']='other.example'
    else:value['Answer']=value['Answer']*17
    with pytest.raises(ValueError):dns._addresses(json.dumps(value),HOST)

@pytest.mark.parametrize('mode',['valid','redirect','compressed','oversize','wrong_type','tls'])
async def test_doh_http_transport_is_fixed_proxyless_and_bounded(monkeypatch,mode):
    seen=[]
    async def handler(request):
        seen.append(request)
        assert str(request.url).startswith('https://1.1.1.1/dns-query?')
        assert dict(request.url.params)=={'name':HOST,'type':'A'}
        assert request.headers['accept']=='application/dns-json' and request.headers['accept-encoding']=='identity'
        assert 'authorization' not in request.headers and 'cookie' not in request.headers
        if mode=='tls':raise httpx.ConnectError('certificate failed',request=request)
        headers={'content-type':'application/dns-json'};body=json.dumps(answer()).encode()
        if mode=='redirect':return httpx.Response(302,headers={'Location':'https://127.0.0.1/private'})
        if mode=='compressed':headers['content-encoding']='gzip'
        if mode=='oversize':body=b'x'*16385
        if mode=='wrong_type':headers['content-type']='text/html'
        return httpx.Response(200,headers=headers,stream=httpx.ByteStream(body))
    factory=httpx.AsyncClient
    def client(**kwargs):
        assert kwargs=={'trust_env':False,'follow_redirects':False,'timeout':5}
        return factory(**kwargs,transport=httpx.MockTransport(handler))
    monkeypatch.setattr(dns.httpx,'AsyncClient',client)
    if mode=='valid':assert await dns.cloudflare_addresses(HOST,allowed_hosts={HOST})
    else:
        with pytest.raises(ValueError):await dns.cloudflare_addresses(HOST,allowed_hosts={HOST})
    assert len(seen)==1

async def test_system_dns_private_failure_never_calls_doh(monkeypatch):
    monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',AsyncMock(return_value=[(socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',('198.18.0.1',443))]))
    doh=AsyncMock(side_effect=AssertionError('system must not switch to DoH'))
    monkeypatch.setattr(dns,'cloudflare_addresses',doh)
    with pytest.raises(ValueError,match='private'):await assets._download('https://bbs.hycdn.cn/image.png')
    doh.assert_not_called()

async def test_download_deadline_includes_doh_and_tls_is_not_relaxed(monkeypatch):
    resolver=dns.cloudflare_addresses
    async def delayed(*args,**kwargs):await asyncio.sleep(1)
    monkeypatch.setattr(dns,'cloudflare_addresses',delayed)
    with pytest.raises(TimeoutError):await assets._download('https://bbs.hycdn.cn/image.png',dns_resolver='cloudflare',timeout_seconds=.01)
    with pytest.raises(ValueError):await resolver('accounts.example',allowed_hosts={HOST})

from datetime import datetime, timedelta, timezone
import json
import httpx
import pytest
from game_assistant.qq.client import InternalQqClient, QqClientError
from game_assistant.qq.models import InboundMessage, QqIdentity

@pytest.mark.asyncio
async def test_single_binding_message_passes_trusted_message_id_and_never_returns_receipt():
    requests=[]
    def respond(request):
        requests.append(request)
        return httpx.Response(200,json={'status':'linked','link_id':'private-link'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client=InternalQqClient('http://127.0.0.1:8000','fixture',http=http)
        now=datetime.now(timezone.utc)
        identity=QqIdentity('app','group','group','sender')
        message=InboundMessage(identity,'trusted-message','绑定 CODE',now.isoformat(),(now+timedelta(minutes=5)).isoformat())
        reply=await client.execute(message)
        assert '绑定成功' in reply and '我的总览' in reply
        assert all(value not in reply for value in ('CODE','private-link','回执','填回'))
        assert requests[0].url.path=='/internal/qq/link-redemptions'
        assert json.loads(requests[0].content)=={'identity':{'app_id':'app','scene':'group','group_openid':'group','sender_openid':'sender'},'code':'CODE','message_id':'trusted-message'}

@pytest.mark.asyncio
@pytest.mark.parametrize('code,status,want',[
    ('qq_link_code_invalid',400,'重新生成'),('qq_link_code_expired',400,'过期'),
    ('qq_link_code_used',409,'使用'),('qq_rate_limited',429,'稍后'),
    ('qq_identity_already_linked',409,'其他网站账号'),('qq_link_owner_unavailable',403,'网站账号'),
])
async def test_binding_failure_explains_next_step_without_raw_details(code,status,want):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(status,json={'detail':code,'secret':'forbidden'}))) as http:
        client=InternalQqClient('http://127.0.0.1:8000','fixture',http=http)
        message=InboundMessage(QqIdentity('app','group','group','sender'),'trusted','绑定 CODE','','')
        text=await client.execute(message)
        assert want in text
        assert code not in text and 'forbidden' not in text and 'CODE' not in text

@pytest.mark.asyncio
async def test_malformed_binding_success_does_not_claim_linked():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,json={'status':'pending','challenge':'old'}))) as http:
        client=InternalQqClient('http://127.0.0.1:8000','fixture',http=http)
        message=InboundMessage(QqIdentity('app','group','group','sender'),'trusted','绑定 CODE','','')
        with pytest.raises(QqClientError):await client.execute(message)

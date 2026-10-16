"""Official SDK adapter plus loopback HTTP business client; no private game store."""
import asyncio
import base64
from dataclasses import asdict, dataclass
from importlib import import_module
from importlib.metadata import version, PackageNotFoundError
from ipaddress import ip_address
import logging
import re
from io import BytesIO
import warnings
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from .commands import parse_command
from .rendering import ImagePreparationFailed
from .transport import instant, utcnow

API_BASE='https://api.bot.qq.com'
SDK_VERSION='1.2.2'
MAX_REPLY_PIXELS = 16_000_000
logger=logging.getLogger(__name__)
BINDING_ERRORS = {
    'qq_link_code_invalid':'绑定码无效，请在网站重新生成后再发送。',
    'qq_link_code_expired':'绑定码已过期，请在看板重新生成，再发送「绑定 新绑定码」。',
    'qq_link_code_revoked':'绑定码已更换，请使用看板最新生成的绑定指令。',
    'qq_link_code_used':'绑定码已使用，请在看板查看已关联身份；如需新关联，请重新生成绑定码。',
    'qq_rate_limited':'绑定请求过于频繁，请稍后再试。',
    'qq_identity_already_linked':'当前 QQ 已关联其他网站账号，请登录原网站账号解除关联后再绑定。',
    'qq_link_owner_unavailable':'网站账号暂不可用，请联系管理员核查后重新生成绑定码。',
    'qq_link_revoked':'此关联已解除，请在看板重新生成绑定码。',
    'qq_message_replay_invalid':'绑定消息无效，请在看板重新生成绑定码后重新发送。',
}
# Fixed refusals of the operator's group policy (group_settings.py); any other detail stays generic.
GROUP_POLICY_ERRORS = {
    'group_game_disabled':'本群未开放这款游戏的查询。',
    'group_select_allowed_game':'本群只开放了部分游戏，请在指令前写明要查的游戏。',
    'group_rate_limited':'本群查询过于频繁，请一分钟后再试。',
}


def valid_reply_image(data, *, max_bytes, max_pixels=MAX_REPLY_PIXELS):
    """Validate bounded static PNG/JPEG bytes, never a path or URL loader."""
    if (not isinstance(data,bytes) or not data or len(data)>min(max_bytes,1048576)
            or not (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff'))):return False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(data),formats=('PNG','JPEG')) as image:
                if image.width<=0 or image.height<=0 or image.width>1080 or image.height>16000 or image.width*image.height>max_pixels or getattr(image,'n_frames',1)!=1:
                    return False
                image.verify()
            with Image.open(BytesIO(data),formats=('PNG','JPEG')) as image:image.load()
        return True
    except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombWarning,Image.DecompressionBombError,SyntaxError):return False


class QqClientError(Exception):
    """A stable error code only; SDK and remote exception strings never propagate."""


@dataclass(frozen=True, slots=True)
class QqReply:
    text: str
    image: bytes | None = None


async def _log_upload_response(response):
    """Observe the official upload response without exposing remote text or IDs."""
    request=response.request
    url=request.url
    if (request.method!='POST' or url.scheme!='https' or url.host!='api.bot.qq.com'
            or url.port not in (None,443)
            or not re.fullmatch(r'/v2/(?:groups|users)/[A-Za-z0-9_-]{1,256}/files',url.path)):
        return
    status=response.status_code
    if type(status) is not int or not 100<=status<=599:return
    # AsyncClient.request already reads this body before returning it to the SDK.
    # aread caches the same bytes; neither the response nor SDK JSON is replaced.
    await response.aread()
    try:data=response.json()
    except (ValueError,UnicodeError):data=None
    code=data.get('code') if isinstance(data,dict) else None
    safe_code=code if type(code) is int and 0<=code<=2**31-1 else 'unavailable'
    logger.log(logging.WARNING if status>=400 else logging.INFO,
        'QQ image upload response: http_status=%d api_code=%s',status,safe_code)


def load_sdk():
    try:
        if version('qqbot-agent-sdk')!=SDK_VERSION:raise ValueError()
        for dependency in ('aiohttp','httpx','cryptography'):import_module(dependency)
        sdk=import_module('qqbot_agent_sdk')
        api=import_module('qqbot_agent_sdk.api_client')
    except (ImportError,PackageNotFoundError,ValueError):
        raise QqClientError('qq_sdk_unavailable_install_qq_extra') from None
    # The empirically verified current official endpoints override obsolete SDK defaults.
    api.API_BASE=API_BASE
    api.TOKEN_URL=API_BASE+'/app/getAppAccessToken'
    for name in ('qqbot_agent_sdk','httpx','httpcore'):
        log=logging.getLogger(name)
        log.handlers=[logging.NullHandler()]
        log.propagate=False
        for child in list(logging.Logger.manager.loggerDict):
            if child.startswith(name+'.'):logging.getLogger(child).disabled=True
    return sdk


class InternalQqClient:
    def __init__(self,base_url,service_token,*,internal_host=None,http=None,images_enabled=False,max_image_bytes=524288):
        url=urlsplit(base_url)
        try:loopback=ip_address(url.hostname or '').is_loopback
        except ValueError:loopback=False
        if not loopback or url.scheme not in ('http','https') or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
            raise QqClientError('qq_internal_endpoint_must_be_literal_loopback')
        if not service_token:raise QqClientError('qq_service_token_required')
        if internal_host is not None:
            # Only a configured authority goes into Host, never into the actual network destination.
            host_url=urlsplit('https://'+internal_host)
            try:port=host_url.port
            except ValueError:raise QqClientError('qq_internal_host_invalid') from None
            if (not re.fullmatch(r'[A-Za-z0-9.\-:\[\]]{1,256}',internal_host)
                    or not host_url.hostname or host_url.username or host_url.password or host_url.path
                    or host_url.query or host_url.fragment or (port is not None and not 1<=port<=65535)):
                raise QqClientError('qq_internal_host_invalid')
        self.internal_host=internal_host
        self.base_url,self.service_token=base_url.rstrip('/'),service_token
        self.http=http or httpx.AsyncClient(timeout=20,trust_env=False,follow_redirects=False)
        self.owns_http=http is None
        self.images_enabled,self.max_image_bytes=images_enabled,max_image_bytes

    async def post(self,path,body):
        try:
            headers={'Authorization':'Bearer '+self.service_token}
            if self.internal_host is not None:headers['Host']=self.internal_host
            response=await self.http.post(self.base_url+path,json=body,headers=headers)
            if response.status_code!=200:
                known=BINDING_ERRORS if path=='/internal/qq/link-redemptions' else GROUP_POLICY_ERRORS
                error=response.json().get('detail')
                if error in known:raise QqClientError(error)
                raise QqClientError('qq_internal_request_failed')
            data=response.json()
            if not isinstance(data,dict):raise ValueError()
            return data
        except QqClientError:
            raise
        except Exception:
            raise QqClientError('qq_internal_request_failed') from None

    async def execute(self,message):
        command=parse_command(message.content)
        identity=asdict(message.identity)
        if command.command=='binding':
            try:
                result=await self.post('/internal/qq/link-redemptions',{'identity':identity,'code':command.code,'message_id':message.message_id})
            except QqClientError as error:
                if str(error) in BINDING_ERRORS:return BINDING_ERRORS[str(error)]
                raise
            if result.get('status')!='linked':
                raise QqClientError('qq_binding_response_invalid')
            return '绑定成功。发送「我的总览」查看本人数据，或发送对应游戏的查询指令。'
        body={'identity':identity,'command':command.command,'game':command.game}
        if getattr(command,'role_name',None) is not None:body['role_name']=command.role_name
        if command.page!=1:body['page']=command.page
        if self.images_enabled:
            body.update(image_requested=True,render_budget_seconds=max(0,min(10,(instant(message.reply_deadline)-utcnow()).total_seconds()-15)))
        try:
            result=await self.post('/internal/qq/query',body)
        except QqClientError as error:
            if str(error) in GROUP_POLICY_ERRORS:return GROUP_POLICY_ERRORS[str(error)]
            raise
        if not isinstance(result.get('text'),str) or len(result['text'])>2500:
            raise QqClientError('qq_query_response_invalid')
        if self.images_enabled and isinstance(result.get('image'),str):
            try:
                if len(result['image'])>4*((self.max_image_bytes+2)//3):raise ValueError()
                image=base64.b64decode(result['image'],validate=True)
                if not valid_reply_image(image,max_bytes=self.max_image_bytes):raise ValueError()
                return QqReply(result['text'],image)
            except ValueError:
                pass
        return result['text']

    async def aclose(self):
        if self.owns_http:await self.http.aclose()


class OfficialQqClient:
    """SDK owns token lifecycle, gateway heartbeat, reconnect and session resume."""
    def __init__(self,app_id,app_secret,gate,dispatcher,*,sdk=None):
        self.sdk=sdk or load_sdk()
        self.gate,self.dispatcher=gate,dispatcher
        self.api=self.sdk.QQApiClient(app_id,app_secret,log_tag='game-assistant')
        self.http=httpx.AsyncClient(timeout=20,trust_env=False,event_hooks={'response':[_log_upload_response]})
        self.api.setup(self.http)
        self.session=[None,None]
        self.ws=None
        self.fatal=None
        self.ready=asyncio.Event()
        self.heartbeat=asyncio.Event()
        self.now=utcnow
        self.max_image_bytes=524288

    async def send_text(self,message,text,sequence):
        if sequence!=1:raise QqClientError('qq_reply_sequence_invalid')
        target=message.identity.group_openid if message.identity.scene=='group' else message.identity.sender_openid
        kind='groups' if message.identity.scene=='group' else 'users'
        try:
            data=await self.api.request('POST',f'/v2/{kind}/{target}/messages',
                {'content':text,'msg_type':0,'msg_id':message.message_id,'msg_seq':sequence})
            if not isinstance(data,dict) or not isinstance(data.get('id'),str) or not data['id']:
                raise ValueError()
            return data['id']
        except Exception:
            raise QqClientError('qq_send_outcome_uncertain') from None

    async def send_image(self,message,image:bytes,sequence:int)->str:
        # Static PNG/JPEG bytes only. Never use SDK URL/path auto-loaders.
        if sequence!=1 or not valid_reply_image(image,max_bytes=self.max_image_bytes):
            raise ImagePreparationFailed('qq_image_invalid')
        target=message.identity.group_openid if message.identity.scene=='group' else message.identity.sender_openid
        kind='groups' if message.identity.scene=='group' else 'users'
        remaining=(instant(message.reply_deadline)-self.now()).total_seconds()
        if remaining<=5:raise ImagePreparationFailed('qq_image_deadline')
        try:
            # srv_send_msg=False ensures even an ambiguous upload cannot deliver a reply.
            uploaded=await asyncio.wait_for(self.api.request('POST',f'/v2/{kind}/{target}/files',
                {'file_type':1,'file_data':base64.b64encode(image).decode('ascii'),'srv_send_msg':False}),timeout=min(20,remaining-5))
            file_info=uploaded.get('file_info') if isinstance(uploaded,dict) else None
            if not isinstance(file_info,str) or not file_info or len(file_info)>16384:raise ValueError()
        except asyncio.TimeoutError:
            raise ImagePreparationFailed('qq_image_upload_timeout') from None
        except Exception as error:
            if isinstance(error,httpx.TimeoutException) or isinstance(error.__cause__,(TimeoutError,httpx.TimeoutException)):
                raise ImagePreparationFailed('qq_image_upload_timeout') from None
            raise ImagePreparationFailed('qq_image_upload_failed') from None
        remaining=(instant(message.reply_deadline)-self.now()).total_seconds()
        if remaining<=0:raise ImagePreparationFailed('qq_image_deadline')
        # file_info is deliberately never cached: each reply uploads anew, so platform
        # TTL and account revocation cannot reuse previously uploaded private media.
        try:
            data=await asyncio.wait_for(self.api.request('POST',f'/v2/{kind}/{target}/messages',
                {'msg_type':7,'media':{'file_info':file_info},'msg_id':message.message_id,'msg_seq':sequence}),timeout=min(20,remaining))
            if not isinstance(data,dict) or not isinstance(data.get('id'),str) or not data['id']:raise ValueError()
            return data['id']
        except Exception:
            raise QqClientError('qq_send_outcome_uncertain') from None

    async def run(self,*,duration=None):
        loop=asyncio.get_running_loop()
        self.fatal=asyncio.Event()
        async def event(kind,data):
            message=self.gate.parse(kind,data)
            if message is not None:await self.dispatcher.handle_message(message)
        def connected():
            logging.getLogger(__name__).info('QQ gateway connected')
            loop.call_soon_threadsafe(self.ready.set)
        def heartbeat():loop.call_soon_threadsafe(self.heartbeat.set)
        def ready(data):
            user=getattr(data,'user',None)
            if isinstance(user,dict):self.gate.bot_openid=user.get('id')
            else:self.gate.bot_openid=getattr(user,'id',None)
        def fatal(code,body):
            logging.getLogger(__name__).error('QQ gateway stopped')
            loop.call_soon_threadsafe(self.fatal.set)
        callbacks=self.sdk.WSCallbacks(on_message_event=event,on_connected=connected,
            on_disconnected=lambda:logging.getLogger(__name__).info('QQ gateway disconnected'),on_fatal_error=fatal,
            get_token=self.api.ensure_token_sync,get_gateway_url=self.api.get_gateway_url_sync,
            clear_token=self.api.clear_token,get_session=lambda:tuple(self.session),
            set_session=lambda sid,seq:self.session.__setitem__(slice(None),[sid,seq]),
            set_heartbeat_interval=lambda seconds:None,fail_pending=lambda reason:None,
            on_ready=ready,on_heartbeat_ack=heartbeat)
        try:
            gateway=await self.api.get_gateway_url()
            self.ws=self.sdk.QQWebSocket(callbacks=callbacks,log_tag='game-assistant')
            self.ws.start(gateway,loop)
            # A swallowed SDK thread error must not leave a silent indefinitely idle bot.
            await asyncio.wait_for(self.ready.wait(),timeout=40)
            if duration is None:await self.fatal.wait()
            else:
                try:await asyncio.wait_for(self.fatal.wait(),timeout=duration)
                except asyncio.TimeoutError:return
            raise QqClientError('qq_gateway_stopped')
        except asyncio.CancelledError:raise
        except Exception:
            raise QqClientError('qq_gateway_failed') from None
        finally:
            if self.ws is not None:await self.ws.async_stop()

    async def aclose(self):await self.http.aclose()

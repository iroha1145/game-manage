"""Website binding routes and loopback-only independent QQ service authentication."""
import hmac
from ipaddress import ip_address
from typing import Literal
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.responses import JSONResponse
from game_assistant.identity.dependencies import require_user
from .bindings import QqBindingService, QqBindingError
from .models import QqIdentity

class IdentityBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    app_id:str=Field(min_length=1,max_length=256)
    scene:Literal['group','c2c']
    group_openid:str|None=Field(default=None,min_length=1,max_length=256)
    sender_openid:str=Field(min_length=1,max_length=256)

    @model_validator(mode='after')
    def valid_identity(self):
        self.identity()
        return self

    def identity(self):
        return QqIdentity(self.app_id,self.scene,self.group_openid,self.sender_openid)

class AttemptBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    identity:IdentityBody
    code:str=Field(min_length=1,max_length=128)

class RedemptionBody(AttemptBody):
    message_id:str=Field(min_length=1,max_length=256)

class ConfirmationBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    identity:IdentityBody
    challenge:str=Field(min_length=1,max_length=128)

class QqServiceAuthenticator:
    def __init__(self,token):
        self._token=token

    def __call__(self,request:Request):
        if not self._token or not request.url.path.startswith('/internal/qq/'):
            return False
        try:
            if request.client is None or not ip_address(request.client.host).is_loopback:return False
        except ValueError:return False
        headers=request.headers.getlist('authorization')
        if len(headers)!=1 or not headers[0].startswith('Bearer '):return False
        # Compare bytes to accept/reject arbitrary header content without Unicode errors.
        return hmac.compare_digest(headers[0][7:].encode(),self._token.encode())


def install_qq_routes(app,*,app_id=None,service_token=None):
    """Install independent bindings (no account query dependency or secret minting)."""
    from game_assistant.cloud_app import allow_cloud_route
    settings=app.state.settings
    app_id=getattr(settings,'qq_app_id','') if app_id is None else app_id
    service_token=getattr(settings,'qq_service_token','') if service_token is None else service_token
    service=QqBindingService(app.state.identity.store,app_id=app_id)
    app.state.qq_bindings=service
    app.state.service_authenticator=QqServiceAuthenticator(service_token)
    router=APIRouter()

    @app.exception_handler(QqBindingError)
    async def binding_error(request,error):
        return JSONResponse({'detail':error.code},status_code=error.status_code)

    @router.post('/api/qq/link-codes')
    def codes(request:Request):return service.create_link_code(require_user(request))

    @router.get('/api/qq/link-attempts')
    def attempts(request:Request):return service.list_attempts(require_user(request))

    @router.post('/api/qq/link-attempts/{attempt_id}/confirm')
    def confirm(attempt_id:str,body:ConfirmationBody,request:Request):
        return service.confirm(require_user(request),attempt_id,body.challenge,body.identity.identity())

    @router.delete('/api/qq/links/{link_id}')
    def unlink(link_id:str,request:Request):return service.unlink(require_user(request),link_id)

    @router.post('/internal/qq/link-attempts')
    def internal_attempt(body:AttemptBody,request:Request):
        # Defense in depth for callers mounting this router outside CloudBoundary.
        if not QqServiceAuthenticator(service_token)(request):
            raise QqBindingError('service_authentication_required',401)
        return service.create_link_attempt(body.identity.identity(),body.code)

    @router.post('/internal/qq/link-redemptions')
    def internal_redemption(body:RedemptionBody,request:Request):
        if not QqServiceAuthenticator(service_token)(request):
            raise QqBindingError('service_authentication_required',401)
        return service.redeem_link_code(body.identity.identity(),body.code,body.message_id)

    app.include_router(router)
    for route in router.routes:
        allow_cloud_route(app,route.path,route.methods,access='service' if route.path.startswith('/internal/qq/') else 'user')
    return service

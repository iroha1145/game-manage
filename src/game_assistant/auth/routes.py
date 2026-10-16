from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

from .service import LoginError


class SmsRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    mobile: str = Field(min_length=11, max_length=11)
    captcha: dict | None = None


class LoginBodyLimitMiddleware:
    """Caps login and Bilibili-source bodies by the bytes received, so chunked
    requests without Content-Length are limited too."""
    PREFIXES = ('/api/auth/', '/api/sources/bilibili')

    def __init__(self, app, max_bytes=16384): self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith(self.PREFIXES):
            return await self.app(scope, receive, send)
        messages, total = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect': return
            total += len(message.get('body', b''))
            if total > self.max_bytes:
                response = JSONResponse({'detail':'登录请求过大'}, status_code=413,
                    headers={'Cache-Control':'no-store','Pragma':'no-cache','Referrer-Policy':'no-referrer'})
                return await response(scope, receive, send)
            messages.append(message)
            if not message.get('more_body', False): break
        async def replay():
            if messages: return messages.pop(0)
            return await receive()
        return await self.app(scope, replay, send)


class LoginRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    mobile: str = Field(min_length=11, max_length=11)
    code: str = Field(min_length=4, max_length=8)


def install_auth_routes(app, service):
    router = APIRouter(prefix='/api/auth')
    app.add_middleware(LoginBodyLimitMiddleware)

    @app.exception_handler(LoginError)
    async def login_error(request, error):
        headers = {'Retry-After': '60'} if error.status == 429 else None
        return JSONResponse({'detail': error.message}, status_code=error.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        if request.url.path.startswith('/api/auth/bilibili-source/'):
            return JSONResponse({'detail': '登录输入不正确，请检查输入', 'error_code': 'INVALID_INPUT'}, status_code=422)
        if request.url.path.startswith('/api/auth/'):
            return JSONResponse({'detail': '登录参数不正确，请检查手机号和验证码'}, status_code=422)
        return await request_validation_exception_handler(request, error)

    @router.get('/status')
    async def status():
        return service.status()

    @router.post('/{game}/sessions')
    async def start(game: str):
        return await service.start(game)

    @router.post('/{game}/sms')
    async def sms(game: str, body: SmsRequest):
        return await service.sms(game, body.session_id, body.mobile, body.captcha)

    @router.post('/{game}/login')
    async def login(game: str, body: LoginRequest):
        return await service.login(game, body.session_id, body.mobile, body.code)

    @router.delete('/{game}')
    async def logout(game: str):
        return await service.logout(game)

    app.include_router(router)

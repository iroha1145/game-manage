from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .dependencies import require_user
from .models import Principal


class LoginBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterBody(LoginBody):
    invite: str = Field(min_length=1, max_length=128)


class RecoveryBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recovery: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=12, max_length=128)


def install_identity_routes(app):
    router = APIRouter(prefix='/api/identity')

    def set_session(request, response, session):
        response.set_cookie('__Host-ga_session', session.token, max_age=request.app.state.settings.cloud_session_seconds,
                            secure=True, httponly=True, samesite='lax', path='/')
        request.app.state.identity.consume_preauth(request.cookies.get('__Host-ga_preauth'))
        response.delete_cookie('__Host-ga_preauth', secure=True, httponly=True, samesite='lax', path='/')
        return {'user_id': session.principal.user_id, 'is_admin': session.principal.is_admin}

    @router.get('/csrf')
    def csrf(request: Request, response: Response):
        from game_assistant.cloud_app import source_ip
        token, preauth = request.app.state.identity.csrf(request.cookies.get('__Host-ga_session'), request.cookies.get('__Host-ga_preauth'), source_ip(request))
        if preauth:
            response.set_cookie('__Host-ga_preauth', preauth, max_age=900, secure=True, httponly=True, samesite='lax', path='/')
        return {'csrf_token': token}

    @router.post('/register')
    def register(body: RegisterBody, request: Request, response: Response):
        from game_assistant.cloud_app import source_ip
        session = request.app.state.identity.register(body.username, body.password, body.invite,
                    source_ip(request), request.cookies.get('__Host-ga_session'))
        return set_session(request, response, session)

    @router.post('/login')
    def login(body: LoginBody, request: Request, response: Response):
        from game_assistant.cloud_app import source_ip
        session = request.app.state.identity.login(body.username, body.password, source_ip(request),
                                                  request.cookies.get('__Host-ga_session'))
        return set_session(request, response, session)

    @router.post('/recover')
    def recover(body: RecoveryBody, request: Request, response: Response):
        from game_assistant.cloud_app import source_ip
        request.app.state.identity.recover(body.recovery, body.password, source_ip(request))
        response.delete_cookie('__Host-ga_session', secure=True, httponly=True, samesite='lax', path='/')
        return {'status': 'ok'}

    @router.get('/me')
    def me(principal: Principal = Depends(require_user)):
        return {'user_id': principal.user_id, 'is_admin': principal.is_admin}

    @router.get('/sessions')
    def sessions(request: Request, principal: Principal = Depends(require_user)):
        return {'sessions': request.app.state.identity.sessions(principal)}

    @router.delete('/sessions/{session_id}')
    def revoke(session_id: str, request: Request, principal: Principal = Depends(require_user)):
        request.app.state.identity.revoke(principal, session_id)
        return {'status': 'ok'}

    @router.post('/logout')
    def logout(request: Request, response: Response, principal: Principal = Depends(require_user)):
        request.app.state.identity.revoke(principal, request.state.identity_session.session_id)
        response.delete_cookie('__Host-ga_session', secure=True, httponly=True, samesite='lax', path='/')
        return {'status': 'ok'}

    app.include_router(router)

"""Administrator SESSDATA/QR authorization for the shared public collector.

No local credential sidefile is read or provisioned. The existing external
cloud key seals a grant in identity.db with owner/grant/version AAD.
"""
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from game_assistant.accounts.service import transaction
from .bilibili_provider import BilibiliLoginProvider
from .bilibili_service import BilibiliLoginService, BilibiliLoginError, fail
from .store import CredentialStoreError

PREFIX = '/api/admin/bilibili-source/login'
PROVIDER = 'bilibili-public-source'


class CloudBilibiliCredentialStore:
    def __init__(self, credentials):
        self.credentials, self.connection = credentials, credentials.connection

    def load(self):
        # Replacement revokes every previous public-source grant. Never fall
        # back to a disabled/demoted administrator's or older revoked grant.
        row = self.connection.execute(
            "SELECT g.user_id,g.grant_id FROM grants g JOIN users u ON u.user_id=g.user_id "
            "WHERE g.provider=? AND g.state='active' AND u.is_admin=1 AND u.disabled_at IS NULL "
            "ORDER BY g.updated_at DESC,g.grant_id DESC LIMIT 1", (PROVIDER,)).fetchone()
        return self.credentials.load_grant(*row) if row else {}

    def for_session(self, session):
        outer = self
        class OwnedStore:
            def load(self): return outer.load()
            def save(self, values): outer.save_for_session(session, values)
        return OwnedStore()

    def save_for_session(self, session, values):
        from game_assistant.identity.service import timestamp
        try:
            with transaction(self.connection):
                active = self.connection.execute(
                    "SELECT 1 FROM users u JOIN sessions s ON s.user_id=u.user_id "
                    "WHERE u.user_id=? AND u.is_admin=1 AND u.disabled_at IS NULL "
                    "AND s.session_id=? AND s.revoked_at IS NULL AND s.expires_at>?",
                    (session.principal.user_id, session.session_id, timestamp())).fetchone()
                if not active:
                    raise fail('SESSION_EXPIRED', 410)
                grant = str(uuid4())
                sealed = self.credentials.seal_grant(session.principal.user_id, grant, values, 1)
                self.connection.execute("UPDATE grants SET state='revoked',version=version+1 WHERE provider=? AND state='active'", (PROVIDER,))
                self.connection.execute(
                    "INSERT INTO grants(grant_id,user_id,provider,state,encrypted_payload) VALUES(?,?,?,'active',?)",
                    (grant, session.principal.user_id, PROVIDER, sealed))
        except (CredentialStoreError, BilibiliLoginError):
            raise
        except Exception:
            raise CredentialStoreError('授权凭据保存失败') from None


class CloudBilibiliLoginService(BilibiliLoginService):
    def __init__(self, source, identity):
        self.identity, self._owners = identity, {}
        super().__init__(source, provider_factory=BilibiliLoginProvider)

    def _prune(self):
        super()._prune()
        self._owners = {sid: owner for sid, owner in self._owners.items()
                        if sid in self._sessions or sid in self._terminal}

    def live(self, owner):
        current = self.identity.authenticate(owner.token)
        return bool(current and current.principal.is_admin and current.session_id == owner.session_id
                    and current.principal.user_id == owner.principal.user_id)

    def check_owner(self, sid, owner):
        self._prune()
        bound = self._owners.get(sid)
        if (not bound or bound.session_id != owner.session_id
                or bound.principal.user_id != owner.principal.user_id or not self.live(bound)):
            raise fail('SESSION_EXPIRED', 410)
        return bound

    async def start_for(self, owner, mode='qr', *, is_disconnected):
        result = await self.start(mode, is_disconnected=is_disconnected)
        self._owners[result['session_id']] = owner
        return result

    def _commit_verified_account(self, session, account):
        owner = self._owners.get(session.sid)
        if not owner or not self.live(owner):
            self._retire(session, 'cancelled')
            raise fail('SESSION_EXPIRED', 410)
        store = self.source.credentials.for_session(owner)
        return self.source.commit_verified_account(account, credential_store=store)


class StartBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['qr','cookie']


class SessdataBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sessdata: SecretStr = Field(min_length=1, max_length=4096)


def install_cloud_bilibili_routes(app, service):
    from game_assistant.cloud_app import allow_cloud_route
    def admin(request):
        owner = app.state.identity.authenticate(request.cookies.get('__Host-ga_session'))
        if not owner: raise HTTPException(401, 'authentication_required')
        if not owner.principal.is_admin: raise HTTPException(403, 'admin_required')
        return owner

    def disconnected(request, owner):
        async def check():
            return not service.live(owner) or await request.is_disconnected()
        return check

    router = APIRouter(prefix=PREFIX)
    @router.get('/status')
    async def status(request: Request):
        admin(request)
        return service.status()
    @router.post('/sessions')
    async def start(body: StartBody, request: Request):
        owner = admin(request)
        return await service.start_for(owner, body.mode, is_disconnected=disconnected(request, owner))
    @router.get('/sessions/{sid}')
    async def status_session(sid: str, request: Request):
        service.check_owner(sid, admin(request))
        return service.session_status(sid)
    @router.delete('/sessions/{sid}')
    async def cancel(sid: str, request: Request):
        service.check_owner(sid, admin(request))
        return await service.cancel(sid)
    @router.post('/sessions/{sid}/qr/poll')
    async def poll(sid: str, request: Request):
        owner = service.check_owner(sid, admin(request))
        return await service.qr_poll(sid, is_disconnected=disconnected(request, owner))
    @router.post('/sessions/{sid}/commit')
    async def commit(sid: str, request: Request):
        owner = service.check_owner(sid, admin(request))
        return await service.commit(sid, is_disconnected=disconnected(request, owner))
    @router.post('/sessions/{sid}/cookie')
    async def cookie(sid: str, body: SessdataBody, request: Request):
        owner = service.check_owner(sid, admin(request))
        return await service.cookie(sid, {'sessdata':body.sessdata.get_secret_value()},
                                    is_disconnected=disconnected(request, owner))
    app.include_router(router)
    for route in router.routes:
        allow_cloud_route(app, route.path, route.methods)

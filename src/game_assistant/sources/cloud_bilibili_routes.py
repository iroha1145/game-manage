"""Administrator-only, bounded collection controls for configured public UIDs."""
import time
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictBool


class RefreshBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    backfill: StrictBool


def install_cloud_bilibili_collection_routes(app, source, scheduler):
    from game_assistant.cloud_app import allow_cloud_route
    router = APIRouter(prefix='/api/admin/bilibili-source')

    def admin(request):
        session = app.state.identity.authenticate(request.cookies.get('__Host-ga_session'))
        if not session:
            raise HTTPException(401, 'authentication_required')
        if not session.principal.is_admin:
            raise HTTPException(403, 'admin_required')

    @router.get('/status')
    async def status(request: Request):
        admin(request)
        result = []
        for item in source.statuses() if source else []:
            # Never expose reason text, diagnostic dictionaries, raw payloads,
            # upstream messages or anything from the credential store.
            values = {key: item[key] for key in ('game_id','uid','pages','failures',
                'last_attempt','last_success','history_complete','coverage_since',
                'next_retry','history_days','total','article_count') if key in item}
            queue = scheduler.public_refresh_state(item['game_id'])
            if queue == 'idle' and time.time() < item.get('next_retry', 0):
                queue = 'cooldown' if item.get('status') == 'ok' else 'backoff'
            state = item.get('status', 'idle')
            if state not in ('idle','ok','error','running'):
                state = 'error'
            if state == 'running' and queue not in ('running','queued'):
                state = 'error'  # Persisted running after interruption is not live.
            diagnostic = item.get('diagnostic')
            if isinstance(diagnostic, dict):
                for key, low, high in (('http_status',100,599),('business_code',-(2**31),2**31-1)):
                    value = diagnostic.get(key)
                    if type(value) is int and low <= value <= high:
                        values[key] = value
            result.append({**values, 'status':state, 'queue_state':queue,
                'running':queue == 'running', 'queued':queue == 'queued'})
        return {'sources':result}

    @router.post('/{game}/refresh')
    async def refresh(game: str, body: RefreshBody, request: Request):
        admin(request)
        return asdict(scheduler.request_bilibili_refresh(game, body.backfill))

    app.include_router(router)
    for route in router.routes:
        allow_cloud_route(app, route.path, route.methods)

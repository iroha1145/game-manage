"""Blueprint collection stays on this computer and never submits codes to the game."""
from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse

from .endfield_blueprints import BlueprintInput, BlueprintStore


def install_endfield_blueprint_routes(app, settings):
    store = BlueprintStore(settings.db_path)
    router = APIRouter(prefix='/api/endfield/blueprints')

    @router.get('')
    async def collection():
        return {'items': store.items()}

    @router.get('/export')
    async def export():
        return JSONResponse({'format': 'game-assistant-endfield-blueprints', 'version': 1,
                             'items': store.items()}, headers={
            'Content-Disposition': 'attachment; filename="endfield-blueprints.json"'})

    @router.post('', status_code=201)
    async def create(body: BlueprintInput):
        try:
            return store.save(body)
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @router.put('/{identity}')
    async def update(identity: str, body: BlueprintInput):
        try:
            return store.save(body, identity)
        except KeyError:
            raise HTTPException(404, '这条蓝图收藏不存在') from None

    @router.delete('/{identity}')
    async def remove(identity: str):
        if not store.delete(identity):
            raise HTTPException(404, '这条蓝图收藏不存在')
        return {'deleted': True}

    app.include_router(router)


def install_cloud_endfield_blueprint_routes(app, boundary):
    """Install scoped cloud routes; the legacy local router stays separate."""
    from game_assistant.private_routes import _install_blueprints
    _install_blueprints(boundary, app)

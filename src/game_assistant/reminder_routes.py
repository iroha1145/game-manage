"""Authenticated rule/inbox and operator-only group settings API."""
from fastapi import APIRouter, Depends, HTTPException, Path

from .identity.dependencies import require_user
from .reminder_policy import ReminderRule
from .group_settings import GroupSettings


SUPPORT = dict(delivery='inbox', external_delivery='unsupported', timezone='Asia/Shanghai')


def install_reminder_routes(app, reminders, groups):
    from .cloud_app import allow_cloud_route
    router = APIRouter()

    def scope(principal, account_id, role_id):
        return reminders.accounts.require_scope(principal, account_id, role_id)

    def admin(principal=Depends(require_user)):
        # Re-read current operator status, including demotion/disable after login.
        with app.state.identity.store.connect() as db:
            app.state.identity._admin(db, principal)
        return principal

    @router.get('/api/accounts/{account_id}/roles/{role_id}/reminders')
    async def rule(account_id: str, role_id: str, principal=Depends(require_user)):
        current = scope(principal, account_id, role_id)
        info = reminders.accounts.describe(current, active=False)
        return dict(rule=reminders.get_rule(current).model_dump(), game=info['game'], **SUPPORT)

    @router.put('/api/accounts/{account_id}/roles/{role_id}/reminders')
    async def save_rule(account_id: str, role_id: str, body: ReminderRule, principal=Depends(require_user)):
        try:
            saved = reminders.set_rule(scope(principal, account_id, role_id), body)
        except ValueError:
            raise HTTPException(422, 'unsupported_rule') from None
        return dict(rule=saved.model_dump(), **SUPPORT)

    @router.get('/api/accounts/{account_id}/roles/{role_id}/reminders/inbox')
    async def inbox(account_id: str, role_id: str, principal=Depends(require_user)):
        return dict(messages=reminders.inbox(scope(principal, account_id, role_id)), **SUPPORT)

    @router.get('/api/admin/qq/groups/{group_openid}/settings')
    async def group(group_openid: str = Path(min_length=1, max_length=256), principal=Depends(admin)):
        return dict(settings=groups.read(app.state.settings.qq_app_id, group_openid).model_dump(), external_delivery='unsupported',
                    public_subscriptions='configuration_only', management='website_operator_admin')

    @router.put('/api/admin/qq/groups/{group_openid}/settings')
    async def save_group(body: GroupSettings, group_openid: str = Path(min_length=1, max_length=256), principal=Depends(admin)):
        return dict(settings=groups.save(app.state.settings.qq_app_id, group_openid, body).model_dump(), external_delivery='unsupported',
                    public_subscriptions='configuration_only', management='website_operator_admin')

    app.include_router(router)
    for route in router.routes:
        allow_cloud_route(app, route.path, route.methods)

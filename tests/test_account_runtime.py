import pytest

from game_assistant.accounts.runtime import AccountRuntime
from game_assistant.config import Settings
from game_assistant.identity.models import Principal
from tests.test_account_auth import authorize, setup


async def test_two_accounts_do_not_share_settings(tmp_path):
    db, store, accounts, login = setup(tmp_path)
    await authorize(login)
    await authorize(login, 'b', '13900000000')
    template = Settings(nte_access_token='legacy', wuwa_token='legacy-kuro', endfield_hg_token='legacy-hg')
    runtime = AccountRuntime(accounts, template, tmp_path / 'runtime', login=login)
    registries = []
    for user in ('a', 'b'):
        row = accounts.list_accounts(Principal(user, False))[0]
        scope = accounts.require_scope(Principal(user, False), row['account_id'], row['roles'][0]['role_id'])
        registries.append(runtime.for_scope(scope))
    sa, sb = [r.get('nte')._settings for r in registries]
    assert sa.nte_access_token == 'token-13800000000'
    assert sb.nte_access_token == 'token-13900000000'
    assert sa is not sb and sa.db_path != sb.db_path
    assert sa.wuwa_token == sa.endfield_hg_token == ''
    assert template.nte_access_token == 'legacy'
    assert [a.game_id for a in registries[0].all()] == ['nte']
    await runtime.aclose()


async def test_skland_runtime_reads_verified_role_with_distinct_cred(tmp_path, monkeypatch):
    from game_assistant.models import Capability
    from game_assistant.adapters.endfield import skland_client
    db,store,accounts,login = setup(tmp_path)
    p = Principal('a',False)
    result = accounts.save_verified(p,'skland',{'user_id':'sk-user','role_id':'sk-role','server_id':'1','cred':'sk-secret'})
    scope = accounts.require_scope(p,result['account_id'],result['role_id'])
    class Client:
        async def refresh(self,cred):
            assert cred == 'sk-secret'
            return 'short-token'
        async def card(self,cred,token,role,server,user,device):
            assert (role,server,user) == ('sk-role','1','sk-user')
            return {'base':{'roleId':'sk-role','name':'Skland player'}}
    monkeypatch.setattr(skland_client,'SklandClient',Client)
    runtime = AccountRuntime(accounts,Settings(endfield_hg_token='legacy'),tmp_path/'runtime',login=login)
    fetched = await runtime.for_scope(scope).get('endfield').fetch(Capability.ACCOUNT)
    assert fetched.ok and fetched.payload['base']['role_id'] == 'sk-role'
    assert fetched.payload['stamina']['current'] is None
    assert 'sk-secret' not in str(fetched.payload)
    await runtime.aclose()


async def test_revoked_runtime_cannot_fetch_with_old_token(tmp_path):
    db, store, accounts, login = setup(tmp_path)
    await authorize(login)
    row = accounts.list_accounts(Principal('a', False))[0]
    scope = accounts.require_scope(Principal('a', False), row['account_id'], row['roles'][0]['role_id'])
    runtime = AccountRuntime(accounts, Settings(), tmp_path / 'runtime', login=login)
    registry = runtime.for_scope(scope)
    accounts.revoke(Principal('a', False), row['account_id'])
    from game_assistant.models import Capability
    result = await registry.get('nte').fetch(Capability.ACCOUNT)
    assert not result.ok and result.error_kind == 'auth_expired'
    with pytest.raises(Exception):
        runtime.for_scope(scope)
    await runtime.aclose()


async def test_endfield_runtime_ledger_checks_scope_manifest(tmp_path):
    import sqlite3
    db,store,accounts,login = setup(tmp_path)
    p = Principal('a',False)
    result = accounts.save_verified(p,'hypergryph',{'uid':'hg-uid','role_id':'hg-role','server_id':'1','hg_token':'hg-secret'})
    scope = accounts.require_scope(p,result['account_id'],result['role_id'])
    runtime = AccountRuntime(accounts,Settings(),tmp_path/'runtime',login=login)
    ledger = runtime.for_scope(scope).get('endfield').gacha_store()
    with pytest.raises(PermissionError):
        ledger.summary('another-role')
    path = next((tmp_path/'runtime').glob('*/endfield_gacha/*.sqlite3'))
    with sqlite3.connect(path) as other:
        other.execute("UPDATE private_scope SET user_id='b'")
    with pytest.raises(PermissionError):
        ledger.summary('hg-role')
    await runtime.aclose()

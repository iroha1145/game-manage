"""终末地适配器（respx 离线）：通行证授权 → u8_token → 寻访记录，以及错误分类。"""
import httpx
import pytest
import respx

from game_assistant.adapters.endfield.adapter import EndfieldAdapter
from game_assistant.adapters.endfield.hypergryph import HypergryphClient
from game_assistant.config import Settings
from game_assistant.models import Capability

HG = "https://as.hypergryph.com"
BINDING = "https://binding-api-account-prod.hypergryph.com/account/binding/v1"
EF = "https://ef-webview.hypergryph.com/api/record"
ROLE = {"roleId": "31000001", "nickName": "管理员", "level": 52, "serverId": "1", "serverName": "China", "isDefault": True}


def adapter(tmp_path, **overrides):
    values = dict(db_path=str(tmp_path / "a.db"), endfield_hg_token="hg-secret", endfield_uid="hg-uid",
                  endfield_role_id="31000001")
    values.update(overrides)
    result = EndfieldAdapter(Settings(**values))
    result.sync_interval = 0
    return result


def mock_binding(accounts=None):
    accounts = accounts if accounts is not None else [
        {"uid": "hg-uid", "isOfficial": True, "channelName": "官服", "roles": [ROLE]}]
    return respx.get(BINDING + "/binding_list").respond(200, json={"status": 0, "data": {"list": [
        {"appCode": "endfield", "bindingList": accounts}]}})


def mock_grant():
    mock_binding()
    return respx.post(HG + "/user/oauth2/v2/grant").respond(200, json={"status": 0, "data": {"token": "grant-secret"}})


def mock_records(special_rows):
    u8 = respx.post(BINDING + "/u8_token_by_uid").respond(200, json={"status": 0, "data": {"token": "u8 secret/+"}})
    respx.get(EF + "/weapon/pool").respond(200, json={"code": 0, "data": []})
    char = respx.get(EF + "/char").mock(side_effect=lambda request: httpx.Response(200, json={"code": 0, "data": {
        "list": special_rows if request.url.params["pool_type"] == "E_CharacterGachaPoolType_Special" else [],
        "hasMore": False}}))
    return u8, char


@respx.mock
async def test_gacha_sync_chains_grant_u8_token_and_records(tmp_path):
    grant = mock_grant()
    rows = [{"seqId": str(seq), "charId": "c", "charName": "提弗洛斯" if seq == 3 else "干员", "rarity": 6 if seq == 3 else 4,
             "poolId": "p", "poolName": "冬猎", "isFree": False, "gachaTs": "1788300000000"} for seq in (5, 4, 3, 2, 1)]
    u8, char = mock_records(rows)
    result = await adapter(tmp_path).fetch(Capability.GACHA)
    assert result.ok, result.error
    assert u8.calls[0].request.read() == b'{"uid":"hg-uid","token":"grant-secret"}'
    assert grant.calls[0].request.read() == b'{"token":"hg-secret","appCode":"be36d44aa36bfb5b","type":1}'
    request = char.calls[0].request
    assert request.url.params["token"] == "u8 secret/+" and "u8+secret%2F%2B" in str(request.url)
    assert request.url.params["server_id"] == "1"
    payload = result.payload.model_dump(mode="json")
    assert payload["pools"][0]["since_last_six"] == {"count": 2, "status": "exact"}
    assert "secret" not in str(payload)


@respx.mock
@pytest.mark.parametrize("response", [httpx.Response(401), httpx.Response(200, json={"status": 3, "msg": "登录已过期，请重新登录"})])
async def test_expired_login_is_reported_as_auth_expired(tmp_path, response):
    respx.post(HG + "/user/oauth2/v2/grant").mock(return_value=response)
    result = await adapter(tmp_path).fetch(Capability.GACHA)
    assert (result.ok, result.error_kind) == (False, "auth_expired")
    assert "hg-secret" not in result.error


@respx.mock
async def test_source_errors_and_invalid_records_keep_previous_snapshots(tmp_path):
    mock_grant()
    respx.post(BINDING + "/u8_token_by_uid").respond(200, json={"status": 0, "data": {"token": "u8"}})
    respx.get(EF + "/weapon/pool").respond(200, json={"code": 0, "data": []})
    route = respx.get(EF + "/char").respond(200, json={"code": 0, "data": {"list": [{"seqId": "x"}], "hasMore": False}})
    assert (await adapter(tmp_path).fetch(Capability.GACHA)).error_kind == "invalid_data"
    route.respond(502)
    assert (await adapter(tmp_path).fetch(Capability.GACHA)).error_kind == "source_error"


async def test_missing_login_is_unconfigured(tmp_path):
    subject = adapter(tmp_path, endfield_hg_token="")
    assert not subject.credentials_configured
    for capability in (Capability.ACCOUNT, Capability.GACHA):
        assert (await subject.fetch(capability)).error_kind == "unconfigured"


@respx.mock
async def test_account_uses_the_logged_in_official_role(tmp_path):
    mock_grant()
    route = respx.get(BINDING + "/binding_list").respond(200, json={"status": 0, "data": {"list": [
        {"appCode": "endfield", "bindingList": [{"uid": "hg-uid", "isOfficial": True, "channelName": "官服", "roles": [ROLE]}]}]}})
    result = await adapter(tmp_path).fetch(Capability.ACCOUNT)
    assert result.payload.model_dump() == {"schema_version": 1, "nickname": "管理员", "level": 52, "role_id": "31000001",
                                           "uid": "hg-uid", "server_name": "China", "channel": "官服", "channel_id": "official"}
    route.respond(200, json={"status": 0, "data": {"list": [
        {"appCode": "endfield", "bindingList": [{"uid": "hg-uid", "isOfficial": True, "roles": [{**ROLE, "roleId": "9"}]}]}]}})
    changed = await adapter(tmp_path).fetch(Capability.ACCOUNT)
    assert (changed.error_kind, changed.error) == ("auth_expired", "终末地绑定角色已变化，请在「社区账号」重新登录")


async def test_unexpected_errors_are_logged_by_type_only(tmp_path, monkeypatch, caplog):
    subject = adapter(tmp_path)

    async def boom(*args, **kwargs):
        raise RuntimeError("https://ef-webview.hypergryph.com/?token=hg-secret")

    monkeypatch.setattr(subject, "fetch_gacha", lambda: subject._guarded_run(boom))
    result = await subject.fetch(Capability.GACHA)
    assert (result.ok, result.error_kind) == (False, "invalid_data")
    assert "RuntimeError" in caplog.text and "hg-secret" not in caplog.text


@respx.mock
async def test_skland_code_requests_a_skland_grant_code():
    grant = respx.post(HG + "/user/oauth2/v2/grant").respond(200, json={"status": 0, "data": {"code": "grant-code"}})
    async with HypergryphClient() as client:
        assert await client.skland_code("hg-secret") == "grant-code"
    assert grant.calls[0].request.read() == b'{"token":"hg-secret","appCode":"4ca99fa6b56cc2ba","type":0}'


@respx.mock
async def test_bilibili_gacha_validates_binding_and_keeps_china_server(tmp_path):
    mock_grant()
    mock_binding([{"uid": "hg-uid", "channelMasterId": "2", "isOfficial": False,
                   "channelName": "bilibili服", "roles": [ROLE]}])
    u8, char = mock_records([])
    result = await adapter(tmp_path, endfield_channel="bilibili", endfield_server_id="1").fetch_gacha()
    assert result.ok, result.error
    assert u8.called and char.calls[0].request.url.params["server_id"] == "1"


@respx.mock
@pytest.mark.parametrize("override", [
    {"uid": "different"}, {"channelMasterId": "2", "isOfficial": False, "channelName": "bilibili服"},
    {"roles": [{**ROLE, "serverId": "2"}]}, {"roles": [{**ROLE, "isBanned": True}]}])
async def test_gacha_refuses_changed_identity_before_requesting_u8(tmp_path, override):
    mock_grant()
    mock_binding([{**{"uid": "hg-uid", "isOfficial": True, "roles": [ROLE]}, **override}])
    u8 = respx.post(BINDING + "/u8_token_by_uid").respond(200, json={"status": 0, "data": {"token": "u8"}})
    result = await adapter(tmp_path).fetch_gacha()
    assert not result.ok and result.error_kind == "auth_expired"
    assert not u8.called


@respx.mock
async def test_account_keeps_saved_role_when_upstream_default_changes(tmp_path):
    mock_grant()
    mock_binding([{"uid": "hg-uid", "isOfficial": True, "roles": [
        {**ROLE, "roleId": "different", "isDefault": True}, {**ROLE, "isDefault": False}]}])
    result = await adapter(tmp_path).fetch_account()
    assert result.ok and result.payload.role_id == ROLE["roleId"]

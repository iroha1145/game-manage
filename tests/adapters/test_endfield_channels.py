"""Synthetic binding responses; no live login or game credentials."""
import pytest

from game_assistant.adapters.endfield.channels import binding_channel
from game_assistant.adapters.endfield.parse import RoleChangedError, select_role, select_official_role
from game_assistant.adapters.endfield.skland_parse import parse_roles

ROLE = {"roleId": "r", "serverId": "1", "nickName": "管理员"}


def binding(*accounts):
    return {"list": [{"appCode": "endfield", "bindingList": list(accounts)}]}


@pytest.mark.parametrize("metadata,expected", [
    ({"channelMasterId": 1}, "official"), ({"channelMasterId": "2"}, "bilibili"),
    ({"isOfficial": True}, "official"), ({"isOfficial": False, "channelName": "bilibili服"}, "bilibili"),
    ({}, "unknown"), ({"isOfficial": False}, "unknown"),
    ({"isOfficial": False, "channelName": "其他服"}, "unknown"),
    ({"channelMasterId": 3, "isOfficial": True}, "unknown"),
    ({"channelMasterId": 2, "isOfficial": True}, "unknown"),
    ({"channelMasterId": 1, "isOfficial": False}, "unknown"),
    ({"channelMasterId": 2, "channelName": "官服"}, "unknown"),
    ({"channelMasterId": 1, "channelName": "bilibili服"}, "unknown"),
    ({"channelMasterId": True, "isOfficial": True}, "unknown"),
    ({"channelMasterId": 2, "isOfficial": 0}, "unknown"),
])
def test_channel_metadata_requires_known_nonconflicting_evidence(metadata, expected):
    assert binding_channel(metadata) == expected


def test_select_channel_does_not_cross_accounts_or_choose_banned_role():
    data = binding({"uid": "official", "isOfficial": True, "roles": [ROLE]},
                   {"uid": "bili", "channelMasterId": 2, "roles": [
                       {**ROLE, "roleId": "banned", "isDefault": True, "isBanned": True}, ROLE]})
    assert select_official_role(data).uid == "official"
    assert select_role(data, "bilibili").uid == "bili"
    assert select_role(data, "bilibili").role_id == "r"
    with pytest.raises(RoleChangedError):
        select_role(data, "bilibili", expected_uid="official", expected_role_id="r", expected_server_id="1")


@pytest.mark.parametrize("marker", ["isDeleted", "isDelete", "isBanned"])
def test_deleted_or_banned_roles_cannot_be_selected(marker):
    with pytest.raises(ValueError):
        select_role(binding({"uid": "u", "isOfficial": True, "roles": [{**ROLE, marker: True}]}))


def test_skland_roles_preserve_uid_and_unknown_channel():
    roles = parse_roles(binding({"uid": "u", "roles": [ROLE]},
                               {"uid": "b", "isOfficial": False, "channelName": "bilibili服", "roles": [ROLE]}))
    assert roles[0]["uid"] == "u" and roles[0]["channel_id"] == "unknown"
    assert roles[0]["channel"] == "unknown" and roles[0]["channel_name"] is None
    assert roles[1]["uid"] == "b" and roles[1]["channel_id"] == "bilibili"
    assert roles[1]["channel"] == "bilibili" and roles[1]["channel_name"] == "bilibili服"



def test_skland_official_role_has_canonical_channel_and_separate_display_name():
    role = parse_roles(binding({"uid": "u", "isOfficial": True, "channelName": "官服", "roles": [ROLE]}))[0]
    assert role["channel"] == role["channel_id"] == "official"
    assert role["channel_name"] == "官服" and role["channel_master_id"] == "1"

"""鹰角绑定接口的终末地渠道标识；未知或矛盾的来源不推断成官服。"""


def binding_channel(binding: dict) -> str:
    raw_id = binding.get("channelMasterId")
    channel_id = str(raw_id).strip() if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool) else ""
    official = binding.get("isOfficial")
    name = binding.get("channelName")
    if raw_id is not None:
        if channel_id == "1" and (official is None or official is True) and name != "bilibili服":
            return "official"
        if channel_id == "2" and (official is None or official is False) and name != "官服":
            return "bilibili"
        return "unknown"
    if official is True and name != "bilibili服":
        return "official"
    if official is False and name == "bilibili服":
        return "bilibili"
    return "unknown"


def channel_master_id(channel: str) -> str:
    return {"official": "1", "bilibili": "2"}.get(channel, "")

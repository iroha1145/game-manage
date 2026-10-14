"""Verified QQ transport identity, deliberately distinct from numeric QQ IDs."""
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class QqIdentity:
    app_id: str
    scene: str
    group_openid: str | None
    sender_openid: str

    def __post_init__(self):
        for value in (self.app_id, self.sender_openid):
            if not isinstance(value,str) or not value.strip() or len(value)>256:
                raise ValueError('Invalid QQ identity')
        if self.scene not in {'group','c2c'}:
            raise ValueError('Invalid QQ scene')
        if self.scene=='group':
            if not isinstance(self.group_openid,str) or not self.group_openid.strip() or len(self.group_openid)>256:
                raise ValueError('Invalid QQ group')
        elif self.group_openid is not None:
            raise ValueError('C2C identity cannot contain a group')

@dataclass(frozen=True, slots=True)
class InboundMessage:
    identity: QqIdentity
    message_id: str
    content: str
    received_at: str
    reply_deadline: str

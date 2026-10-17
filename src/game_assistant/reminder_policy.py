"""Bounded reminder policies; timestamps always describe source reads."""
from datetime import datetime, timezone, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SHANGHAI = timezone(timedelta(hours=8))


class QuietPolicy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    timezone: Literal['Asia/Shanghai'] = 'Asia/Shanghai'
    quiet_start: str | None = Field(default=None, pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    quiet_end: str | None = Field(default=None, pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')

    @model_validator(mode='after')
    def quiet_pair(self):
        if (self.quiet_start is None) != (self.quiet_end is None):
            raise ValueError('quiet interval requires both boundaries')
        if self.quiet_start is not None and self.quiet_start == self.quiet_end:
            raise ValueError('quiet interval must have different boundaries')
        return self


class ReminderRule(QuietPolicy):
    enabled: bool = False
    notify_full: bool = False
    threshold_percent: int | None = Field(default=None, ge=1, le=99)
    city_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    cooldown_seconds: int = Field(default=3600, ge=60, le=7 * 86400)
    daily_cap: int = Field(default=3, ge=1, le=24)
    max_source_age_seconds: int = Field(default=600, ge=60, le=3600)


def in_quiet_time(policy: QuietPolicy, now: datetime) -> bool:
    if policy.quiet_start is None:
        return False
    local = now.astimezone(SHANGHAI).strftime('%H:%M')
    start, end = policy.quiet_start, policy.quiet_end
    return start <= local < end if start < end else local >= start or local < end


def stamina_candidates(payload, rule: ReminderRule, now: datetime) -> list[dict]:
    if not rule.enabled or in_quiet_time(rule, now):
        return []
    data = payload.model_dump() if hasattr(payload, 'model_dump') else payload
    if not isinstance(data, dict) or any(data.get(k) is True for k in ('stale', 'source_delayed')):
        return []
    stamp = data.get('updated_at')
    try:
        read_at = stamp if isinstance(stamp, datetime) else datetime.fromisoformat(stamp)
        if read_at.tzinfo is None or not 0 <= (now - read_at).total_seconds() <= rule.max_source_age_seconds:
            return []
    except (ValueError, TypeError):
        return []
    result = []
    for prefix, label, threshold in [('', '体力', rule.threshold_percent), ('city_', '都市活力', rule.city_threshold_percent)]:
        current, maximum = data.get(prefix + 'current'), data.get(prefix + 'maximum')
        if type(current) is not int or type(maximum) is not int or maximum <= 0 or current < 0:
            continue
        # Items can lift stamina above its maximum; that is still full.
        if not prefix and current >= maximum and rule.notify_full:
            name, title = 'full', '体力已满'
        elif threshold is not None and current * 100 >= maximum * threshold and (prefix or current < maximum):
            name, title = prefix + 'threshold', label + '达到阈值'
        else:
            continue
        result.append(dict(rule=name, title=title, source_read_at=read_at.isoformat(),
            body=f'{label} {current}/{maximum}；读取时间 {read_at.astimezone(SHANGHAI):%Y-%m-%d %H:%M:%S}（北京时间）。'))
    return result

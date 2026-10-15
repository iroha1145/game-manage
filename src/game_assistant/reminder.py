from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone

from game_assistant.config import Settings
from game_assistant.event_calendar import BEIJING_TZ
from game_assistant.models import Capability, FetchResult, GameEvent, StaminaInfo
from game_assistant.reminder_store import ReminderDedup
from game_assistant.reminder_policy import ReminderRule, stamina_candidates

logger = logging.getLogger(__name__)


@dataclass
class Reminder:
    title: str
    body: str
    dedup_key: str


class ReminderEngine:
    """轮询后提醒规则评估；各规则的去重键见方法内注释。"""

    def __init__(self, dedup: ReminderDedup, notifier,
                 settings: Settings) -> None:
        self.dedup = dedup
        self.notifier = notifier
        self._settings = settings
        self._fail_counts: dict[tuple[str, str], int] = {}

    async def deliver(self, r: Reminder) -> bool:
        lease = self.dedup.claim(r.dedup_key)
        if not lease:
            return False
        success = False
        try:
            success = await self.notifier.send(r.title, r.body)
        finally:
            completed = self.dedup.finish(r.dedup_key, lease, success)
        return completed

    async def handle_poll(self, game_id: str, display_name: str,
                          capability: Capability, result: FetchResult,
                          failure_count: int | None = None) -> None:
        settings = self._settings
        now = datetime.now(timezone.utc)
        today = now.astimezone(BEIJING_TZ).strftime("%Y-%m-%d")
        # 规则 1：连续拉取失败（达到阈值后每次失败都会尝试推送，由当日去重限流；成功清零）
        key = (game_id, capability.value)
        if result.error_kind == 'account_changed':
            return
        if not result.ok and result.error_kind in ('offline', 'unconfigured'):
            self._fail_counts.pop(key, None)
            return
        if not result.ok:
            self._fail_counts[key] = (failure_count if failure_count is not None
                                     else self._fail_counts.get(key, 0) + 1)
            n = settings.fail_notify_threshold
            if n > 0 and self._fail_counts[key] >= n:
                await self.deliver(Reminder(
                    f"{display_name} 数据拉取连续失败",
                    f"{capability.value}: {result.error}",
                    f"fetch_fail:{game_id}:{capability.value}:{today}"))
            return
        self._fail_counts.pop(key, None)
        # 规则 2/3：体力满 / 体力阈值
        if isinstance(result.payload, StaminaInfo):
            await self._stamina_rules(game_id, display_name, result.payload,
                                      today, settings, now)
        # 规则 4：活动日历临期（版本公告解析/手填的 list[GameEvent]，逐活动评估）
        if isinstance(result.payload, list) and result.payload and \
                all(isinstance(e, GameEvent) for e in result.payload):
            await self._events_rule(game_id, display_name, result.payload,
                                    settings, now)

    async def _stamina_rules(self, game_id: str, display_name: str,
                             s: StaminaInfo, today: str,
                             settings: Settings, now: datetime) -> None:
        p = settings.stamina_threshold_percent
        policy = ReminderRule(enabled=True, notify_full=settings.notify_stamina_full,
            threshold_percent=p if 1 <= p <= 99 else None,
            city_threshold_percent=settings.nte_city_stamina_threshold_percent or None)
        prefix = {'full':'stamina_full','threshold':'stamina_thres','city_threshold':'city_stamina_thres'}
        for item in stamina_candidates(s, policy, now):
            title = '体力即将回满' if item['rule'] == 'threshold' else item['title']
            await self.deliver(Reminder(display_name+title,item['body'],f"{prefix[item['rule']]}:{game_id}:{today}"))

    async def _events_rule(self, game_id: str, display_name: str,
                           events: list[GameEvent],
                           settings: Settings, now: datetime) -> None:
        # 规则 4：活动日历临期（结束前严格 0 < 秒数 <= N 天；逐活动评估，key 含 name+end_at
        # 的 md5 前 12 位，跨日不重复推）
        if settings.activity_remind_days <= 0:
            return
        for ev in events:
            if ev.end_at is None:
                continue
            # 解析层契约是 aware UTC+8；naive 视为契约破坏：记警告并跳过，
            # 不给未知时区的时间贴北京标签（会错算绝对时刻）
            if ev.end_at.tzinfo is None or (
                    ev.start_at is not None and ev.start_at.tzinfo is None):
                logger.warning("活动「%s」时间戳缺时区，跳过临期提醒", ev.name)
                continue
            end = ev.end_at.astimezone(BEIJING_TZ)
            if ev.start_at is not None and ev.start_at >= end:
                continue
            seconds = (end - now).total_seconds()
            if not (0 < seconds <= settings.activity_remind_days * 86400):
                continue
            remaining = math.ceil(seconds / 86400)
            raw = f"{ev.name}|{end.isoformat()}"
            key12 = hashlib.md5(raw.encode()).hexdigest()[:12]
            await self.deliver(Reminder(
                f"{display_name}活动即将结束",
                f"「{ev.name}」还剩 {remaining} 天（{end:%m-%d %H:%M} 结束）。",
                f"event_exp:{game_id}:{key12}"))

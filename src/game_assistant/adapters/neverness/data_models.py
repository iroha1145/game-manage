"""Versioned, source-faithful Neverness to Everness dashboard payloads."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from game_assistant.models import StaminaInfo, GameEvent


class NteCalendarEvent(GameEvent):
    """Official notice dates retain their source precision through serialization."""
    version: str | None = None
    source: Literal['community'] = 'community'
    source_name: str = '塔吉多官方公告'
    source_url: str | None = None
    published_at: datetime | None = None
    aliases: list[str] = Field(default_factory=list)
    start_date: str | None = None
    start_text: str | None = None
    start_precision: Literal['relative', 'day', 'minute', 'unknown'] | None = None
    start_source: dict[str, JsonValue] | None = None
    start_estimated: bool | None = None
    start_basis: Literal['scheduled_maintenance', 'notice_relative_date'] | None = None
    start_date_precision: Literal['day'] | None = None
    end_date: str | None = None
    end_text: str | None = None
    end_precision: Literal['minute', 'day', 'unknown', 'permanent'] | None = None
    permanent: bool = False
    time_text: str | None = None


class NtePayload(BaseModel):
    schema_version: Literal[1] = 1


class NteAccount(NtePayload):
    nickname: str | None = None
    level: int | None = None
    role_id: str = ""
    server_name: str | None = None
    world_level: int | None = None
    tycoon_level: int | None = None
    active_days: int | None = None
    character_count: int | None = None
    achievement_count: int | None = None
    achievement_total: int | None = None
    house_count: int | None = None
    house_total: int | None = None
    vehicle_count: int | None = None
    vehicle_total: int | None = None


class NteStamina(StaminaInfo):
    schema_version: Literal[1] = 1
    city_current: int | None = None
    city_maximum: int | None = None
    daily_activity: int | None = None
    weekly_remaining: int | None = None


class NteWeapon(BaseModel):
    id: str | None = None
    name: str | None = None
    level: int | None = None
    quality: str | None = None
    mix_level: int | None = None
    breakthrough_level: int | None = None
    group_type: str | None = None
    description: str | None = None
    buff_name: str | None = None
    buff_description: str | None = None
    lbd: JsonValue | None = None
    properties: list['NteProperty'] = Field(default_factory=list)


class NteProperty(BaseModel):
    id: str | None = None
    name: str | None = None
    value: str | None = None


class NteSkillItem(BaseModel):
    title: str | None = None
    desc: str | None = None


class NteSkill(BaseModel):
    id: str | None = None
    type: str | None = None
    name: str | None = None
    level: int | None = None
    items: list[NteSkillItem] = Field(default_factory=list)


class NteEquippedItem(BaseModel):
    id: str | None = None
    name: str | None = None
    level: int | None = None
    main_properties: list[NteProperty] = Field(default_factory=list)
    properties: list[NteProperty] = Field(default_factory=list)
    # The reference API schema does not prove these scoring inputs.
    quality: str | None = None
    area: int | None = None
    substats_complete: bool | None = None


class NteSuit(BaseModel):
    id: str | None = None
    name: str | None = None
    description_two: str | None = None
    description_four: str | None = None
    conditions: JsonValue | None = None
    activation_count: int | None = None
    core: list[NteEquippedItem] = Field(default_factory=list)
    pie: list[NteEquippedItem] = Field(default_factory=list)


class NteRole(BaseModel):
    id: str
    name: str | None = None
    level: int | None = None
    quality: str | None = None
    element: str | None = None
    awaken_level: int | None = None
    mix_level: int | None = None
    affinity_exp: int | None = None
    icon_url: str | None = None
    weapon: NteWeapon | None = None
    properties: list[NteProperty] = Field(default_factory=list)
    skills: list[NteSkill] = Field(default_factory=list)
    city_skills: list[NteSkill] = Field(default_factory=list)
    group_type: str | None = None
    awaken_effects: list[str] = Field(default_factory=list)
    suit: NteSuit | None = None


class NteRoles(NtePayload):
    entries: list[NteRole] = Field(default_factory=list)


class NteCountEntry(BaseModel):
    id: str
    name: str | None = None
    current: int | None = None
    total: int | None = None


class NteProgress(NtePayload):
    completed: int | None = None
    total: int | None = None
    bronze: int | None = None
    silver: int | None = None
    gold: int | None = None
    categories: list[NteCountEntry] = Field(default_factory=list)


class NteArea(NteCountEntry):
    details: list[NteCountEntry] = Field(default_factory=list)


class NteExploration(NtePayload):
    areas: list[NteArea] = Field(default_factory=list)


class NteGachaDetail(BaseModel):
    item_id: str
    name: str
    pity: int | None = None
    obtained_at: datetime | None = None
    lucky_type: int | None = None


class NteGachaPool(BaseModel):
    name: str | None = None
    total_draws: int | None = None
    s_count: int | None = None
    average: float | None = None
    percentile: float | None = None
    guarantee: int | None = None
    details: list[NteGachaDetail] = Field(default_factory=list)


class NteGacha(NtePayload):
    role_id: str = ""
    nickname: str | None = None
    luck_title: str | None = None
    luck_type: int | None = None
    total_draws: int | None = None
    total_s: int | None = None
    pools: list[NteGachaPool] = Field(default_factory=list)


class NteRecordCard(BaseModel):
    game_name: str | None = None
    role_id: str
    nickname: str | None = None
    level: int | None = None
    server_name: str | None = None
    url: str | None = None


class NteRecord(NtePayload):
    cards: list[NteRecordCard] = Field(default_factory=list)

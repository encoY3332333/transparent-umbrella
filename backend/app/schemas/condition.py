"""出行条件（UC-02）的请求 / 响应模型。"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class PartyType(StrEnum):
    """同行人员构成，与 docs/api.md 的枚举保持一致。"""

    SOLO = "SOLO"
    COUPLE = "COUPLE"
    FAMILY = "FAMILY"
    FRIENDS = "FRIENDS"


class TravelConditionIn(BaseModel):
    """录入条件的请求体。

    范围校验放在 service 层做，这样能返回 docs/api.md 里约定的
    CONDITION_* 错误码；Pydantic 只负责类型与必填。
    """

    originCity: str = Field(min_length=1, max_length=50)
    destCity: str = Field(min_length=1, max_length=50)
    startDate: date
    endDate: date
    budget: float
    partySize: int
    partyType: PartyType = PartyType.SOLO
    preferenceTags: list[str] = Field(default_factory=list)
    mustVisit: list[int] = Field(default_factory=list)
    avoidPOI: list[int] = Field(default_factory=list)


class ResolvedCity(BaseModel):
    """城市名解析后的坐标。"""

    city: str
    lat: float
    lng: float


class ResolvedCities(BaseModel):
    origin: ResolvedCity
    dest: ResolvedCity


class BudgetBreakdownHint(BaseModel):
    """预算拆分提示，不涉及真实订单价格。"""

    perDay: float
    perPersonPerDay: float


class ConditionValidationOut(BaseModel):
    """条件校验通过后的摘要。"""

    valid: bool = True
    days: int
    resolved: ResolvedCities
    budgetBreakdownHint: BudgetBreakdownHint
    warnings: list[str] = Field(default_factory=list)

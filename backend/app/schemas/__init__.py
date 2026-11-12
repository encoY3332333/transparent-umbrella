"""Pydantic 模型集中出口。

按用例分文件（本 Issue 只落地 health），统一从这里导出，避免路由里出现深层 import 路径。
"""

from __future__ import annotations

from app.schemas.common import ApiResponse, PageMeta
from app.schemas.condition import (
    BudgetBreakdownHint,
    ConditionValidationOut,
    PartyType,
    ResolvedCities,
    ResolvedCity,
    TravelConditionIn,
)
from app.schemas.health import HealthOut

__all__ = [
    "ApiResponse",
    "BudgetBreakdownHint",
    "ConditionValidationOut",
    "HealthOut",
    "PageMeta",
    "PartyType",
    "ResolvedCities",
    "ResolvedCity",
    "TravelConditionIn",
]

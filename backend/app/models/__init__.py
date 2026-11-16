"""ORM 模型包。

Issue #1 只建立 `Base`；业务表分别由 #5（POI / 拥挤度）、#4（行程）、
#13（策略参数）、#12（反馈）等 Issue 落地。

**新模型必须在这里 import 一次**：测试用 `Base.metadata.create_all()` 建表，
没被 import 的模型不会进 metadata，表就不会被建出来——报错信息往往是
「no such table」，很容易误判成迁移写错。
"""

from __future__ import annotations

from app.models.base import Base
from app.models.itinerary import Activity, Itinerary, ItineraryDay
from app.models.strategy import StrategyParameter

__all__ = [
    "Activity",
    "Base",
    "Itinerary",
    "ItineraryDay",
    "StrategyParameter",
]

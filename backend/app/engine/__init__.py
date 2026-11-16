"""排程引擎包。

**纯净层**：只允许依赖标准库与本包内的 dataclass。
禁止 import `app.models` / `app.adapters` / `sqlalchemy`——
这样排程算法可以脱离数据库与网络单测（architecture.md 分层约束第 3 条）。

Issue #5 已落地候选筛选与拥挤度；Scorer / Packer / Feasibility / BudgetIterator 由 #4 落地。
"""

from __future__ import annotations

from app.engine.crowd import CrowdIndexCalculator, apply_crowd_index, calculate_crowd_index
from app.engine.selector import (
    Candidate,
    CandidateSelector,
    InsufficientPoiData,
    Poi,
    PoiSelectionError,
    SelectionCriteria,
)

__all__ = [
    "Candidate",
    "CandidateSelector",
    "CrowdIndexCalculator",
    "InsufficientPoiData",
    "Poi",
    "PoiSelectionError",
    "SelectionCriteria",
    "apply_crowd_index",
    "calculate_crowd_index",
]

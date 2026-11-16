"""行程生成的三个子模块协议（Issue #4）。

**为什么用 `Protocol` 而不是抽象基类**：`Protocol` 是结构化子类型，
`#5` / `#6` / `#7` 的实现类**不需要显式继承**，只要方法签名对得上就满足类型检查。
三个人并行开发时，谁也不用等谁先定基类，也不会为了「继承关系」去改对方文件。

**纯净层**：本模块不 import fastapi / sqlalchemy / adapters，
这样编排层可以完全脱离数据库与网络做单测（见 tests/services/test_plan_service.py）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable

from app.engine.selector import Candidate, Poi


@dataclass(frozen=True)
class Requirement:
    """经 UC-02 校验后的出行条件（编排层视角）。

    刻意不直接用 `schemas` 里的 Pydantic 模型：engine 层如果依赖 Pydantic，
    就再也做不到「不装 FastAPI 也能跑算法单测」。
    """

    city: str
    start_date: date
    days: int
    budget: float
    party_size: int
    preference_tags: tuple[str, ...] = ()
    must_visit: tuple[int, ...] = ()
    avoid_poi: tuple[int, ...] = ()


@dataclass(frozen=True)
class PlanContext:
    """一次生成过程中在子模块之间传递的只读上下文。

    `weather_by_day` 的 key 允许是 `None`：表示「拿不到天气」的降级统一值。
    调用方必须把它当作「未知」而不是「晴」，否则 BR-08 会被架空。
    """

    requirement: Requirement
    weather_by_day: dict[date | None, str] = field(default_factory=dict)
    travel_matrix: dict[tuple[int, int], int] = field(default_factory=dict)
    degraded_sources: tuple[str, ...] = ()
    # 候选 POI 池。放默认值 `()` 而不是把 `pois` 设成必填，
    # 是为了让只测编排顺序的用例不必造 POI；但真实入口必须传，
    # 空池会被 `CandidateSelector` 判成 `InsufficientPoiData`（宁可报错也不静默出空方案）。
    pois: tuple[Poi, ...] = ()


@dataclass(frozen=True)
class Reason:
    """一条推荐理由。`basis` 写依据（如「BR-09」），便于前端做角标。"""

    text: str
    basis: str


@dataclass(frozen=True)
class ActivityDraft:
    """尚未落库的活动。与 ORM 的 `Activity` 分开，避免 engine 依赖 models。"""

    poi: Poi
    day_index: int
    start_minute: int
    end_minute: int
    travel_minutes: int = 0
    crowd_index: int | None = None
    crowd_shifted: bool = False


@dataclass(frozen=True)
class PlanDraft:
    """一个候选方案（落库前的形态）。"""

    title: str
    activities: tuple[ActivityDraft, ...]
    reasons: tuple[Reason, ...] = ()
    total_cost: float = 0.0
    total_minutes: int = 0


@dataclass(frozen=True)
class Conflict:
    """可行性冲突。`severity` 决定是拦截（`ERROR`）还是仅提示（`WARN`）。"""

    code: str
    message: str
    day_index: int | None = None
    severity: str = "WARN"


@runtime_checkable
class CandidateSelector(Protocol):
    """`#5` 候选 POI 筛选。"""

    def select(self, requirement: Requirement, pois: list[Poi]) -> list[Candidate]:
        """返回带拥挤度的候选集。结果不足时应抛 `InsufficientPoiData`。"""
        ...


@runtime_checkable
class PlanPacker(Protocol):
    """`#6` 排程引擎。"""

    def plan(
        self,
        requirement: Requirement,
        candidates: list[Candidate],
        context: PlanContext,
    ) -> list[PlanDraft]:
        """返回 1–3 套方案。全部不可行时返回空列表，由编排层抛 `PLAN_INFEASIBLE`。"""
        ...


@runtime_checkable
class FeasibilityChecker(Protocol):
    """`#7` 可行性校验。"""

    def validate(self, plan: PlanDraft) -> list[Conflict]:
        """返回冲突列表。空列表表示通过；含 `severity="ERROR"` 的项应被编排层丢弃。"""
        ...


__all__ = [
    "ActivityDraft",
    "CandidateSelector",
    "Conflict",
    "FeasibilityChecker",
    "PlanContext",
    "PlanDraft",
    "PlanPacker",
    "Reason",
    "Requirement",
]

"""把 `#6` 的排程引擎接到 `#4` 的编排协议上（Issue #4）。

**为什么需要这一层**：两边是并行开发的，接口天然不一样，而且不该为了「好看」
去改对方的类。四组差异（左 `#6`，右 `#4`）：

- 入口：`StrategyEngine.plan(candidates, request)` ↔
  `PlanPacker.plan(requirement, candidates, context)`
- 输入：`PlanRequest(start_date, days, tourist, weather_by_day, travel_minutes)` ↔
  `Requirement` + `PlanContext`
- 输出：`PlanResult(days, reasons, weights, poi_ids)` ↔
  `PlanDraft(title, activities, reasons, total_cost, total_minutes)`
- 活动：`Activity(poi_id, start: time, end: time, …)` ↔
  `ActivityDraft(poi: Poi, start_minute, end_minute, …)`

四个必须翻译的点：

1. `Requirement` → `PlanRequest`，其中 `TouristProfile` 由偏好标签与总预算拼出来；
2. `Activity.poi_id` → `ActivityDraft.poi`：`#6` 的 Activity 只存 id 不存对象，
   要从候选池反查；查不到就**丢弃该活动并记日志**，而不是塞一个假 POI
   （假 POI 会让 #4 落库时写入错误的名字与价格）。
3. `time` → 当日分钟数：`#4` 的 ORM 存 `start_minute`（见 `models/itinerary.py`）。
4. `reasons: tuple[str]` → `tuple[Reason]`：`#6` 的理由是纯文本，
   首项形如「【均衡】」，这里拆成 `text` + `basis=""`，不臆造规则编号。

**纯净层不受影响**：本模块在 `app/services/`，允许 import 两边；`app/engine/` 不动。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from app.engine.protocols import (
    ActivityDraft,
    Candidate,
    PlanContext,
    PlanDraft,
    PlanPacker,
    Reason,
    Requirement,
)
from app.engine.selector import Poi

logger = logging.getLogger(__name__)


class _StrategyEngineLike(Protocol):
    """只声明本模块用到的那个方法，便于测试注入假实现。

    不直接 `from app.engine.strategy_engine import StrategyEngine` 作为类型：
    `#6` 未合入时那个模块不存在，会连 `import` 都失败。
    """

    def plan(
        self,
        candidates: Sequence[Candidate],
        request: Any,
        *,
        must_visit: Sequence[int] = ...,
    ) -> list[Any]: ...


# `#6` 的「方案标签」写在 reasons 首项的【】里（源标签是
# `_VARIANT_SPECS` 的 "均衡方案" / "省钱方案" / "偏好方案"），用它给方案起标题。
# 键带「方案」后缀，同时容忍不带后缀的写法——两边都不改对方的命名习惯。
_TITLE_BY_LABEL = {
    "均衡方案": "均衡推荐线",
    "省钱方案": "省钱优先线",
    "偏好方案": "偏好深度线",
}


class StrategyEnginePacker:
    """`PlanPacker` 的实现：内部调用 `#6` 的 `StrategyEngine`。"""

    def __init__(self, engine: _StrategyEngineLike | None = None) -> None:
        if engine is None:
            # 延迟到构造函数里 import：`#6` 的引擎模块由 `build_packer()` 兜住
            # ImportError，模块级 import 会让整个应用在未合入时起不来。
            from app.engine.strategy_engine import StrategyEngine

            engine = StrategyEngine()
        self._engine = engine

    # ------------------------------------------------------------------
    def plan(
        self,
        requirement: Requirement,
        candidates: list[Candidate],
        context: PlanContext,
    ) -> list[PlanDraft]:
        request = _build_request(requirement, context)

        results = self._engine.plan(candidates, request, must_visit=requirement.must_visit)

        by_id: dict[int, Poi] = {c.poi.id: c.poi for c in candidates}
        drafts: list[PlanDraft] = []
        for index, result in enumerate(results):
            draft = self._to_draft(result, requirement, by_id, index)
            if draft.activities:
                drafts.append(draft)
            else:
                # 整套方案一个活动都没落成，给用户看只会是空白行程，不如不给
                logger.warning("第 %d 套方案没有可落库的活动，已跳过", index + 1)
        return drafts

    # ------------------------------------------------------------------
    def _to_draft(
        self,
        result: Any,
        requirement: Requirement,
        by_id: dict[int, Poi],
        index: int,
    ) -> PlanDraft:
        reasons = tuple(getattr(result, "reasons", ()) or ())
        activities: list[ActivityDraft] = []
        total_minutes = 0

        for day_index, day in enumerate(getattr(result, "days", ())):
            total_minutes += int(getattr(day, "total_minutes", 0) or 0)
            # `day_index` 必须来自 enumerate 的下标，不能用 `day.day` 反算：
            # 行程中间某天被整体跳过时，反算会得到越界下标，落库时抛 ValueError。
            for act in getattr(day, "activities", ()) or ():
                poi = by_id.get(act.poi_id)
                if poi is None:
                    logger.warning(
                        "活动 %s（poi_id=%s）不在候选池里，已丢弃",
                        getattr(act, "name", "?"),
                        act.poi_id,
                    )
                    continue
                activities.append(
                    ActivityDraft(
                        poi=poi,
                        day_index=day_index,
                        start_minute=_to_minute(act.start),
                        end_minute=_to_minute(act.end),
                        travel_minutes=int(getattr(act, "travel_minutes", 0) or 0),
                        crowd_index=getattr(act, "crowd_index", None),
                        crowd_shifted=bool(getattr(act, "crowd_shifted", False)),
                    )
                )

        return PlanDraft(
            title=self._title(requirement, reasons, index),
            activities=tuple(activities),
            reasons=_to_reasons(reasons),
            total_cost=float(getattr(result, "total_cost", 0.0) or 0.0),
            total_minutes=total_minutes,
        )

    @staticmethod
    def _title(requirement: Requirement, reasons: tuple[str, ...], index: int) -> str:
        """标题形如「西安 4 日 · 均衡推荐线」。

        从 `#6` 的 reasons[0] 里取【】中的标签；取不到就退回「方案 N」，
        不猜一个听起来像真的名字。
        """
        label = ""
        if reasons:
            head = reasons[0].strip()
            if head.startswith("【") and "】" in head:
                label = head[1 : head.index("】")].strip()
        # 先按原样查，再去掉「方案」后缀查一次；都没有就退回「方案 N」，
        # 不去猜一个听起来像真的名字。
        suffix = (
            _TITLE_BY_LABEL.get(label)
            or _TITLE_BY_LABEL.get(label.removesuffix("方案"))
            or f"方案 {index + 1}"
        )
        return f"{requirement.city} {requirement.days} 日 · {suffix}"


@dataclass(frozen=True)
class _TouristFallback:
    """`#6` 的 `TouristProfile` 的结构替身。"""

    preference_tags: frozenset[str] = frozenset()
    budget: float = 1000.0


@dataclass(frozen=True)
class _PlanRequestFallback:
    """`#6` 的 `PlanRequest` 的结构替身。"""

    start_date: date
    days: int
    tourist: _TouristFallback
    weather_by_day: Mapping[date | None, str]
    travel_minutes: Mapping[tuple[int, int], int] | None = None


def _build_request(requirement: Requirement, context: PlanContext) -> Any:
    """构造 `#6` 的 `PlanRequest`。

    **优先用 `#6` 的真类，import 不到就用结构等价的替身**。
    这样做是为了让本 Issue 不被 PR #32 的合并状态卡住：
    `StrategyEngine.plan()` 只读 `request.start_date / .days / .tourist.* /
    .weather_by_day / .travel_minutes` 这几个属性，没有 `isinstance` 检查，
    替身与真类在运行时无法区分（已有测试守住字段名一致）。
    `#32` 合入后这里会自动改用真类，行为不变也不需要改代码。
    """
    try:
        # `app.engine.scorer` 的 `TouristProfile` 只有 `preference_tags / budget /
        # 其他可选字段`，与 `_TouristFallback` 结构等价；两条路径都保留，是为了让
        # 本 Issue 不依赖 `#6` 的合并顺序（`#6` 现已合入，走真类分支）。
        from app.engine.scorer import TouristProfile
        from app.engine.strategy_engine import PlanRequest

        tourist_cls: Any = TouristProfile
        request_cls: Any = PlanRequest
    except ImportError:  # pragma: no cover - 只在 #6 未合入时走到
        tourist_cls = _TouristFallback
        request_cls = _PlanRequestFallback

    return request_cls(
        start_date=requirement.start_date,
        days=requirement.days,
        tourist=tourist_cls(
            preference_tags=frozenset(requirement.preference_tags),
            # `#6` 用总预算把门票价格归一化到 [0,1]；传人均会把省钱方案算偏，
            # 所以这里传总预算，与 SRS「总预算」口径一致。
            budget=requirement.budget,
        ),
        weather_by_day=context.weather_by_day,
        # 空 dict 与 None 在 `#6` 里等价（都当「没有路网数据」），
        # 但传 None 更明确，避免被误判成「有矩阵只是全 0」。
        travel_minutes=context.travel_matrix or None,
    )


def _to_minute(value: Any) -> int:
    """`datetime.time` → 当日分钟数。

    也接受已经是 int 的输入，方便测试用整数构造假数据。
    越界值不在这里 clamp——落库时 `_persist` 会校验 day_index，
    时间越界由 #7 的可行性校验负责，本层不重复实现规则。
    """
    if isinstance(value, int):
        return value
    return int(value.hour) * 60 + int(value.minute)


def _to_reasons(reasons: tuple[str, ...]) -> tuple[Reason, ...]:
    """纯文本理由 → `Reason`。

    `basis` 留空而不是填「BR-xx」：`#6` 的理由文本里并没写依据哪条规则，
    凭空补一个规则编号比留空更糟——评审时无法核查。
    """
    return tuple(Reason(text=text, basis="") for text in reasons if text.strip())


def build_packer() -> PlanPacker | None:
    """尝试装配真实的排程引擎；不可用返回 None 由调用方回落到占位实现。"""
    try:
        return StrategyEnginePacker()
    except ImportError:
        logger.warning("排程引擎（#6 / PR #32）尚未合入，将使用占位实现")
        return None


__all__ = ["StrategyEnginePacker", "build_packer"]

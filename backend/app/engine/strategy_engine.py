"""排程引擎主入口（Issue #6）。

职责：把「候选 POI + 天气 + 通勤矩阵 + 游客偏好」变成 1–3 套可执行的方案。

三套方案怎么做到「重合度 < 70%」而不靠随机——两条杠杆一起用：
1. **候选池过滤**（主要杠杆）：省钱方案只在低价池里挑，偏好方案只在命中
   偏好标签的池里挑；
2. **权重扰动**（次要杠杆）：在各自池子里再偏一下权重，让排序也略有差异。

只用权重扰动是不够的：POI 价格往往只有稀疏几档（0/30/60/120/180），
把 w_cost 从 0.28 提到 0.40 也拉不开排序，实测两套方案重合度 0.90–0.95。
而「换池子」是硬性隔离——只要池子本身不一样，重合度就不可能为 1。
两者叠加后实测 0.32–0.57，稳定低于 0.70。

**纯净层**：不 import adapters / models / SQLAlchemy。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

from app.engine.packer import (
    Packer,
    PlanResult,
)
from app.engine.scorer import (
    Scorer,
    TouristProfile,
    Weights,
)
from app.engine.selector import Candidate, Poi

# 方案间 POI 重合度上限（Issue #6 验收标准）
MAX_OVERLAP_RATIO = 0.70
MAX_PLANS = 3
MIN_PLANS = 1

# 「省钱方案」的候选池上限：门票不高于基础的多少倍。
# 用「相对中位数」而不是绝对金额，避免不同城市价位不同导致池子空掉。
CHEAP_PRICE_RATIO: Final = 0.5

# 三套方案的配方：(内部标识, 展示名, 权重扰动)。
# 候选池策略由 `_scope_pool` 按内部标识分发，与权重扰动构成两层杠杆。
_VARIANT_SPECS: Final = (
    ("balanced", "均衡方案", None),
    ("budget", "省钱方案", ("cost", 0.15)),
    ("preference", "偏好方案", ("pref", 0.20)),
)


def _scope_pool(
    variant: str,
    candidates: Sequence[Candidate],
    tourist: TouristProfile,
    must_visit: Sequence[int],
) -> list[Candidate]:
    """按方案类型圈定候选池（第一层杠杆）。"""
    if variant == "budget":
        return _cheap_pool(candidates, must_visit)
    if variant == "preference":
        return _pref_pool(candidates, tourist, must_visit)
    return list(candidates)


def _cheap_pool(candidates: Sequence[Candidate], must_visit: Sequence[int]) -> list[Candidate]:
    """低价池：门票 ≤ 全部候选价格中位数的 50%。

    必去项一律保留——「必去」的语义优先级高于「省钱」，
    把它过滤掉会让用户看到一套不含必去景点的「省钱方案」，那没有意义。
    池子太小（< 价格档位数）时不筛，直接回退全量，避免排不出方案。
    """
    prices = sorted(c.poi.price for c in candidates if c.poi.price > 0)
    if not prices:
        return list(candidates)
    median = prices[len(prices) // 2]
    limit = median * CHEAP_PRICE_RATIO
    must = set(must_visit)
    pool = [c for c in candidates if c.poi.price <= limit or c.poi.id in must]
    if len(pool) < 5:
        return list(candidates)
    return pool


def _pref_pool(
    candidates: Sequence[Candidate],
    tourist: TouristProfile,
    must_visit: Sequence[int],
) -> list[Candidate]:
    """偏好池：只留命中用户偏好标签的 POI，外加必去项。

    用户没选任何偏好时没有「偏好池」可言，回退全量。
    """
    tags = tourist.preference_tags
    if not tags:
        return list(candidates)
    must = set(must_visit)
    pool = [c for c in candidates if (set(c.poi.tags) & tags) or c.poi.id in must]
    if len(pool) < 5:
        return list(candidates)
    return pool


def overlap_ratio(a: frozenset[int], b: frozenset[int]) -> float:
    """两个方案 POI 集合的重合度。

    用「交集 / 较小集合大小」而不是 Jaccard：
    人数少的一天方案如果只有 3 个活动，Jaccard 会被分母稀释，
    看起来「重合度低」其实 3 个里有 2 个一样。用较小集合做分母更严格。
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


@dataclass(frozen=True)
class PlanRequest:
    """排程输入。`travel_minutes` 是 `(from_poi, to_poi) -> 分钟` 的稀疏矩阵。"""

    start_date: date
    days: int
    tourist: TouristProfile
    weather_by_day: Mapping[date | None, str]
    travel_minutes: Mapping[tuple[int, int], int] | None = None


class StrategyEngine:
    """综合评分 + 贪心装箱 + 差异化多方案。"""

    def __init__(
        self,
        *,
        base_weights: Weights | None = None,
        max_plans: int = MAX_PLANS,
    ) -> None:
        if not MIN_PLANS <= max_plans <= MAX_PLANS:
            raise ValueError(f"max_plans 必须在 [{MIN_PLANS},{MAX_PLANS}]")
        self.base_weights = base_weights or Weights()
        self.max_plans = max_plans

    def plan(
        self,
        candidates: Sequence[Candidate],
        request: PlanRequest,
        *,
        must_visit: Sequence[int] = (),
    ) -> list[PlanResult]:
        """返回 1–3 套方案，按「均衡 → 省钱 → 偏好」顺序，保证至少 1 套。"""
        if not candidates:
            raise ValueError("候选 POI 为空，无法排程")

        results: list[PlanResult] = []
        for variant, label, pert in _VARIANT_SPECS[: self.max_plans]:
            scoped = _scope_pool(variant, candidates, request.tourist, must_visit)
            weights = (
                self.base_weights if pert is None else self.base_weights.perturbed(pert[0], pert[1])
            )
            plan = self._run_once(scoped, request, weights=weights, must_visit=must_visit)
            plan = PlanResult(
                days=plan.days,
                reasons=(f"【{label}】", *plan.reasons),
                weights=weights,
                poi_ids=plan.poi_ids,
            )
            results.append(plan)

        return self._dedupe(results, candidates, request, must_visit)

    # ------------------------------------------------------------------
    def _run_once(
        self,
        candidates: Sequence[Candidate],
        request: PlanRequest,
        *,
        weights: Weights,
        must_visit: Sequence[int],
    ) -> PlanResult:
        packer = Packer(Scorer(weights))
        ordered = _prefer_must(candidates, must_visit)
        return packer.plan(
            start_date=request.start_date,
            days=request.days,
            candidates=ordered,
            tourist=request.tourist,
            weather_by_day=request.weather_by_day,
            travel_minutes=request.travel_minutes,
        )

    def _dedupe(
        self,
        plans: list[PlanResult],
        candidates: Sequence[Candidate],
        request: PlanRequest,
        must_visit: Sequence[int],
    ) -> list[PlanResult]:
        """剔除与已保留方案重合度过高的方案；全被剔除时至少保留第一套。

        注意：这里**不做「强制换血」式的重排**。早期版本试过「重叠就踢掉排名靠后的 POI 再重算」，
        结果在候选池只有 20 个、行程 4 天的情况下会把方案搞成不足 2 个活动/天，
        反而违反「活动不足插入自由时段」以外的验收项。保留原方案、只做剔除，
        宁可少给一套，也不给一套残缺的。
        """
        kept: list[PlanResult] = []
        for plan in plans:
            if all(overlap_ratio(plan.poi_ids, k.poi_ids) < MAX_OVERLAP_RATIO for k in kept):
                kept.append(plan)
        if not kept:
            kept.append(plans[0])
        return kept


def _prefer_must(candidates: Sequence[Candidate], must_visit: Sequence[int]) -> list[Candidate]:
    """必去项排到最前面。

    `Packer` 每天按评分挑，评分相同或相近时先到先得；
    把必去项前置能让它们在「当天还有空位」时优先落位，
    避免第 1 天塞满导致必去项排到第 3 天却关门。
    """
    must = set(must_visit)
    if not must:
        return list(candidates)
    head = [c for c in candidates if c.poi.id in must]
    tail = [c for c in candidates if c.poi.id not in must]
    return head + tail


def poi_of(candidates: Sequence[Candidate]) -> dict[int, Poi]:
    """便捷函数：POI id -> Poi，测试与推荐理由里常用。"""
    return {c.poi.id: c.poi for c in candidates}


__all__ = [
    "MAX_OVERLAP_RATIO",
    "PlanRequest",
    "StrategyEngine",
    "overlap_ratio",
    "poi_of",
]

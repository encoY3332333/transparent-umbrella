"""行程生成编排（Issue #4）。

这一层**只做编排**，不实现任何算法：

    select（#5 候选筛选） → plan（#6 排程引擎） → validate（#7 可行性）

三条约定，来自 architecture.md 与 Issue #4 技术备注：

1. **事务边界只在这里**。`api/` 层不写 `session.begin()`，路由只管把会话传进来。
2. **不 try/except 包住整个编排**。异常往上抛，由 `core/handlers.py` 统一转成响应；
   只有「需要降级」的特定异常才在本地处理。
3. **子模块通过 Protocol 注入**。`#5`/`#6`/`#7` 没做完时，用假实现就能测编排逻辑。

顺序不能换：`validate` 必须拿到 `plan` 的产出，`plan` 必须拿到 `select` 的候选。
验收标准里那条 `calls == ["select", "plan", "validate"]` 就是防止有人为了「快点出结果」
把 validate 挪到前面（那时还没有方案可校验）。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ErrorCode
from app.engine.protocols import (
    CandidateSelector,
    Conflict,
    FeasibilityChecker,
    PlanContext,
    PlanDraft,
    PlanPacker,
    Reason,
    Requirement,
)
from app.engine.selector import InsufficientPoiData, Poi, PoiSelectionError
from app.models.itinerary import Activity, Itinerary, ItineraryDay, ItineraryStatus

logger = logging.getLogger(__name__)

# 一次生成最多保留几套方案。SRS UC-03 要求 1–3 套，多的截断而不是报错。
MAX_PLANS = 3

# BR-07：两景点间通勤超过 60 分钟要在 UI 上标「长途」。定义在 service 而不是 engine，
# 是因为它是「展示口径」而不是排程口径——engine 只负责算出分钟数。
LONG_TRANSFER_MINUTES = 60


@dataclass
class GeneratedPlan:
    """落库后的一个方案 + 它的可行性提示（未落库，只用于响应）。"""

    itinerary: Itinerary
    conflicts: list[Conflict]


@dataclass
class GenerationResult:
    """一次生成的整体结果。

    把 `duration_ms` / `degraded` 一起返回，而不是让路由层自己再掐一次表——
    路由如果自己计时会漏掉「事务提交」那段，测出来的耗时比真实值小。
    """

    batch_id: str
    plans: list[GeneratedPlan]
    duration_ms: int
    degraded: list[str]


class PlanService:
    """把三个子模块串起来，并把结果原子地写进数据库。"""

    def __init__(
        self,
        *,
        selector: CandidateSelector,
        packer: PlanPacker,
        feasibility: FeasibilityChecker,
    ) -> None:
        self._selector = selector
        self._packer = packer
        self._feasibility = feasibility

    def generate(
        self,
        session: Session,
        requirement: Requirement,
        *,
        context: PlanContext | None = None,
    ) -> GenerationResult:
        """生成 1–3 套方案并落库为 `PROPOSED`。

        `session` 由调用方提供（路由注入），本方法自己开事务。
        """
        started = time.perf_counter()
        batch_id = str(uuid.uuid4())
        ctx = context or PlanContext(requirement=requirement)

        # ---------- 编排：三步，顺序固定 ----------
        # `#5` 的 selector 自带 `InsufficientPoiData` / `PoiSelectionError` 两个异常。
        # engine 是纯净层，不能认识 `ErrorCode`；所以「翻译成业务错误码」这件事
        # 必须在编排层做——否则异常一路冒到 handlers 会变成 500，
        # 用户看到「服务端异常」而真正原因只是「这个城市还没有景点数据」。
        try:
            candidates = self._selector.select(requirement, ctx_pois(ctx, requirement))
        except InsufficientPoiData as exc:
            logger.warning("候选不足：%s", exc)
            shortfall = f"{exc.count} 个，至少需要 {exc.minimum} 个"
            raise BusinessError(
                code=ErrorCode.PLAN_NO_CANDIDATE,
                message=f"{requirement.city} 可用景点不足（{shortfall}）",
            ) from exc
        except PoiSelectionError as exc:
            # 必去/必避撞车属于用户输入问题，用 400 级错误码而不是 422
            logger.warning("候选筛选失败：%s", exc)
            raise BusinessError(
                code=ErrorCode.CONDITION_MUST_VISIT_CONFLICT, message=str(exc)
            ) from exc

        if not candidates:
            raise BusinessError(code=ErrorCode.PLAN_NO_CANDIDATE)

        drafts = self._packer.plan(requirement, candidates, ctx)
        if not drafts:
            raise BusinessError(code=ErrorCode.PLAN_INFEASIBLE)

        accepted: list[tuple[PlanDraft, list[Conflict]]] = []
        for draft in drafts[:MAX_PLANS]:
            conflicts = self._feasibility.validate(draft)
            # 有 ERROR 级冲突的方案直接丢：让用户看到一套「明确不可行」的方案
            # 只会造成困扰，不如少给一套。
            if any(c.severity == "ERROR" for c in conflicts):
                logger.info(
                    "方案 %s 存在 ERROR 级冲突，已丢弃：%s",
                    draft.title,
                    "; ".join(c.message for c in conflicts if c.severity == "ERROR"),
                )
                continue
            accepted.append((draft, conflicts))

        if not accepted:
            raise BusinessError(code=ErrorCode.PLAN_INFEASIBLE)

        # ---------- 落库：一个事务，失败全回滚 ----------
        # `with session.begin()` 而不是手动 commit：中途任何异常都会自动 rollback，
        # 不会留下「行程建了但天没建」这种半成品。
        with session.begin():
            itineraries = [
                self._persist(session, batch_id, requirement, ctx, draft) for draft, _ in accepted
            ]

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "plan.generate.duration_ms=%s plan_id=%s plan_count=%d batch_id=%s city=%s days=%d",
            duration_ms,
            itineraries[0].id,
            len(itineraries),
            batch_id,
            requirement.city,
            requirement.days,
            extra={
                "event": "plan.generate",
                "duration_ms": duration_ms,
                "plan_id": itineraries[0].id,
                "plan_count": len(itineraries),
                "batch_id": batch_id,
            },
        )

        return GenerationResult(
            batch_id=batch_id,
            plans=[
                GeneratedPlan(itinerary=it, conflicts=conflicts)
                for it, (_, conflicts) in zip(itineraries, accepted, strict=True)
            ],
            duration_ms=round(duration_ms),
            degraded=list(ctx.degraded_sources),
        )

    # ------------------------------------------------------------------
    # 落库
    # ------------------------------------------------------------------
    def _persist(
        self,
        session: Session,
        batch_id: str,
        requirement: Requirement,
        ctx: PlanContext,
        draft: PlanDraft,
    ) -> Itinerary:
        itinerary = Itinerary(
            batch_id=batch_id,
            title=draft.title,
            status=ItineraryStatus.PROPOSED,
            city=requirement.city,
            start_date=requirement.start_date,
            days=requirement.days,
            party_size=requirement.party_size,
            budget=requirement.budget,
            total_cost=round(draft.total_cost, 2),
            total_minutes=draft.total_minutes,
            reasons_json=json.dumps(_reasons_payload(draft.reasons), ensure_ascii=False),
            degraded_json=json.dumps(list(ctx.degraded_sources), ensure_ascii=False),
        )

        for day_index in range(requirement.days):
            itinerary.day_plans.append(
                ItineraryDay(
                    day_index=day_index,
                    day_date=requirement.start_date + timedelta(days=day_index),
                )
            )
        days_by_index = {d.day_index: d for d in itinerary.day_plans}

        for act in draft.activities:
            day = days_by_index.get(act.day_index)
            if day is None:
                # 子模块给出了越界的 day_index——这是实现方的 bug，不是用户输入问题，
                # 所以用 ValueError 往上抛（会被 handlers 转成 500），而不是业务错误。
                raise ValueError(
                    f"活动 {act.poi.name} 的 day_index={act.day_index} "
                    f"超出行程天数 {requirement.days}"
                )
            day.activities.append(
                Activity(
                    poi_id=act.poi.id,
                    poi_name=act.poi.name,
                    category=act.poi.category,
                    start_minute=act.start_minute,
                    end_minute=act.end_minute,
                    price=act.poi.price,
                    travel_minutes=act.travel_minutes,
                    crowd_index=act.crowd_index,
                    crowd_shifted=act.crowd_shifted,
                    long_transfer=act.travel_minutes > LONG_TRANSFER_MINUTES,
                )
            )

        session.add(itinerary)
        # flush 而非 commit：拿自增 id 供日志用，事务仍由外层 with 控制
        session.flush()
        return itinerary


def ctx_pois(ctx: PlanContext, requirement: Requirement) -> list[Poi]:
    """从上下文里取候选 POI 池。

    POI 由 `#5` 的仓储提供，`service` 不直接查库（`engine` 是纯净层，不能碰 models），
    所以由调用方把读到的 POI 放进 `PlanContext.pois`。
    没有来源时返回空列表，`selector.select` 会抛 `InsufficientPoiData`——
    这比静默返回空方案更好定位：至少日志里能看出是「池子空了」而不是「算法排不出来」。
    """
    return list(ctx.pois)


def _reasons_payload(reasons: tuple[Reason, ...]) -> list[dict[str, str]]:
    return [{"text": r.text, "basis": r.basis} for r in reasons]


__all__ = [
    "LONG_TRANSFER_MINUTES",
    "MAX_PLANS",
    "GeneratedPlan",
    "GenerationResult",
    "PlanService",
]

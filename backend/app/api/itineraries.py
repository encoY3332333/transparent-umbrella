"""行程生成接口（Issue #4 / UC-03）。

两个出口共用一个 service：

- `POST /api/itineraries/generate` —— JSON，给前端交互与接口测试用；
- `POST /api/itineraries/generate.fragment` —— HTML 片段，给服务端渲染的加载态页用。

**路由层不做业务判断**：只负责「请求体 → `Requirement`」和「结果 → 响应」。
阈值、可行性、打分全在 service / engine ——否则同一套规则在 JSON 与页面两个入口
各写一遍，迟早不一致。
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import plan_service_dep
from app.core.deps import DbDep
from app.core.errors import BusinessError, ErrorCode
from app.engine.protocols import Conflict, PlanContext, Requirement
from app.models.itinerary import Itinerary, ItineraryDay
from app.schemas.common import ApiResponse
from app.schemas.itinerary import (
    ActivityOut,
    ConflictOut,
    GenerateRequest,
    GenerateResponse,
    ItineraryOut,
    OutputDay,
    hhmm,
)
from app.services.plan_service import PlanService
from app.services.poi_repository import PoiRepository
from app.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["itinerary"])

PlanServiceDep = Annotated[PlanService, Depends(plan_service_dep)]


# ----------------------------------------------------------------------
# 请求 → engine
# ----------------------------------------------------------------------
def _requirement(payload: GenerateRequest) -> Requirement:
    """请求模型 → engine 的 `Requirement`。

    `budget` 原样传总预算：人均换算由 engine 做（`budget / party_size / days`），
    路由这边换算一次、engine 再换算一次的话，四舍五入会差几块钱。
    """
    return Requirement(
        city=payload.dest_city,
        start_date=payload.start_date,
        days=payload.days,
        budget=payload.budget,
        party_size=payload.party_size,
        preference_tags=tuple(payload.preference_tags),
        must_visit=tuple(payload.must_visit),
        avoid_poi=tuple(payload.avoid_poi),
    )


def _context(payload: GenerateRequest, requirement: Requirement, session: Session) -> PlanContext:
    """组装上下文：POI 池 + 当前生效的策略权重。

    **权重每次生成都从 UC-09 的策略表取**（`StrategyService` 内部带 60 秒缓存，
    发布/回滚时主动失效），而不是在进程启动时读一次——这正是 AC-1
    「保存后 5 秒内新参数对新发起的规划生效」的实现方式。
    """
    pois = PoiRepository().read_pois(session, requirement.city)
    strategy = StrategyService(session).current()
    return PlanContext(
        requirement=requirement,
        pois=tuple(pois),
        strategy_weights=strategy.engine_weights(),
    )


# ----------------------------------------------------------------------
# ORM → 响应
# ----------------------------------------------------------------------
def _load(session: Session, itinerary_ids: list[int]) -> list[Itinerary]:
    """按 id 重新查一遍，把三层关联一次性 load 出来。

    为什么不直接用 `service` 返回的对象：`with session.begin()` 退出后事务已提交，
    对象处于 detached 状态，访问 `day_plans` / `activities` 会抛 `DetachedInstanceError`
    （`expire_on_commit=False` 只保住已加载的属性，懒加载关系保不住）。
    重查一次带了 `selectinload`，总共 3 条 SQL，代价远小于「在事务里就把 DTO 拼好」
    带来的耦合——那样 service 就得认识 Pydantic。
    """
    stmt = (
        select(Itinerary)
        .where(Itinerary.id.in_(itinerary_ids))
        .options(selectinload(Itinerary.day_plans).selectinload(ItineraryDay.activities))
        .order_by(Itinerary.id)
    )
    return list(session.execute(stmt).scalars().all())


def _to_out(itinerary: Itinerary, conflicts: list[Conflict]) -> ItineraryOut:
    day_warnings: dict[int, list[str]] = defaultdict(list)
    for conflict in conflicts:
        # 只把「具体某一天」的冲突挂到那天；跨天冲突（如总预算超支）
        # 留在方案级，挂到某一天会让人以为那天有问题。
        if conflict.day_index is not None:
            day_warnings[conflict.day_index].append(conflict.message)

    days = [
        OutputDay(
            day_index=day.day_index,
            day_no=day.day_index + 1,
            date=day.day_date,
            activities=[
                ActivityOut(
                    id=act.id,
                    poi_id=act.poi_id,
                    poi_name=act.poi_name,
                    category=act.category,
                    start_time=hhmm(act.start_minute),
                    end_time=hhmm(act.end_minute),
                    start_minute=act.start_minute,
                    end_minute=act.end_minute,
                    cost=round(act.price, 2),
                    travel_minutes=act.travel_minutes,
                    long_transfer=act.long_transfer,
                    crowd_index=act.crowd_index,
                    crowd_shifted=act.crowd_shifted,
                    locked=act.locked,
                    warnings=list(day_warnings.get(day.day_index, ())),
                )
                for act in day.activities
            ],
            # 一天一个活动都没有 = 这天没排上，前端要显示「空闲」占位与建议
            free_slot=not day.activities,
        )
        for day in itinerary.day_plans
    ]

    return ItineraryOut(
        id=itinerary.id,
        title=itinerary.title,
        status=itinerary.status,
        batch_id=itinerary.batch_id,
        city=itinerary.city,
        start_date=itinerary.start_date,
        day_count=itinerary.days,
        party_size=itinerary.party_size,
        budget=round(itinerary.budget, 2),
        total_cost=round(itinerary.total_cost, 2),
        total_minutes=itinerary.total_minutes,
        budget_breakdown={"ticket": _ticket_cost(days)},
        reasons=_parse_reasons(itinerary.reasons_json),
        conflicts=[
            ConflictOut(code=c.code, message=c.message, severity=c.severity, day_index=c.day_index)
            for c in conflicts
        ],
        days=days,
    )


def _ticket_cost(days: list[OutputDay]) -> float:
    return round(sum(a.cost for d in days for a in d.activities), 2)


def _parse_reasons(raw: str) -> list[dict[str, str]]:
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        # 历史数据里可能有手改坏的 JSON；记一条日志、按空处理，
        # 不要因为「推荐理由坏了」就让整个行程打不开。
        logger.warning("reasons_json 解析失败，按空处理：%r", raw[:120])
        return []
    if not isinstance(parsed, list):
        return []
    return [r for r in parsed if isinstance(r, dict)]


# ----------------------------------------------------------------------
# JSON 接口
# ----------------------------------------------------------------------
@router.post(
    "/itineraries/generate",
    response_model=ApiResponse[GenerateResponse],
    summary="生成行程（返回 1–3 套方案）",
)
def generate_itinerary(
    payload: GenerateRequest, session: DbDep, service: PlanServiceDep
) -> ApiResponse[GenerateResponse]:
    requirement = _requirement(payload)
    context = _context(payload, requirement, session)

    result = service.generate(session, requirement, context=context)
    ids = [plan.itinerary.id for plan in result.plans]
    conflicts = {plan.itinerary.id: plan.conflicts for plan in result.plans}

    return ApiResponse.ok(
        GenerateResponse(
            itineraries=[_to_out(it, conflicts[it.id]) for it in _load(session, ids)],
            degraded=result.degraded,
            duration_ms=result.duration_ms,
        )
    )


def _form_to_payload(form: object) -> dict[str, object]:
    """`application/x-www-form-urlencoded` → `GenerateRequest` 能吃的 dict。

    两个坑：

    - `preferenceTags` 是复选框，同名多值，`form.getlist()` 才是完整的；
      用 `form["preferenceTags"]` 只会拿到最后一个。
    - 表单里所有值都是字符串，`budget="6000"` 交给 Pydantic 能自动转，
      但空字符串转 `int` 会报错，所以空值统一丢掉，让字段走默认值。
    """
    getlist = getattr(form, "getlist", None)
    data: dict[str, object] = {}
    for key in form:  # type: ignore[attr-defined]
        if getlist is not None and key == "preferenceTags":
            data[key] = [v for v in getlist(key) if v]
            continue
        raw = form[key]  # type: ignore[index]
        if isinstance(raw, str) and not raw.strip():
            continue
        data[key] = raw
    return data


# ----------------------------------------------------------------------
# HTMX 片段
# ----------------------------------------------------------------------
@router.post(
    "/itineraries/generate.fragment",
    response_class=HTMLResponse,
    include_in_schema=False,
    summary="生成行程（HTMX 片段）",
)
async def generate_fragment(
    request: Request, session: DbDep, service: PlanServiceDep
) -> HTMLResponse:
    """HTMX 版：成功返回结果片段，业务失败也返回**200 + 错误片段**。

    三处与 JSON 接口不同的地方，都是 HTMX 的行为逼出来的：

    1. **不接收 `payload: GenerateRequest`**。HTMX 对 `<form>` 默认发
       `application/x-www-form-urlencoded`，而 Pydantic 模型只从 JSON body 取值，
       声明成参数会得到 `PARAM_INVALID: Input should be a valid dictionary`。
       这里从 `request.form()` 手工转成 dict，再交给同一个模型校验，规则不重复。
    2. **必须是 `async def`**：`request.form()` 是协程。
    3. **业务失败返回 200**。HTMX 默认不 swap 非 2xx 的响应体，
       若让 `BusinessError` 冒到异常处理器，`hx-target` 会被清空，用户什么都看不到。
       这是「需要降级」的特定异常，不属于「把异常吞掉不报」。
    """
    templates = request.app.state.templates
    try:
        form = await request.form()
        payload = GenerateRequest.model_validate(_form_to_payload(form))
        requirement = _requirement(payload)
        context = _context(payload, requirement, session)
        result = service.generate(session, requirement, context=context)
    except ValidationError as exc:
        # 表单校验失败也要渲染成片段，否则用户看到的是一屏 JSON
        details = [
            {"field": ".".join(str(p) for p in err["loc"]), "reason": str(err["msg"])}
            for err in exc.errors()
        ]
        return HTMLResponse(
            templates.get_template("partials/generate_error.html").render(
                request=request,
                code=ErrorCode.PARAM_INVALID.value,
                message="请检查填写的内容",
                details=details,
            )
        )
    except BusinessError as exc:
        logger.info("页面生成失败 %s: %s", exc.code.value, exc.message)
        return HTMLResponse(
            templates.get_template("partials/generate_error.html").render(
                request=request,
                code=exc.code.value,
                message=exc.message,
                details=[{"field": d.field, "reason": d.reason} for d in exc.details],
            )
        )

    ids = [plan.itinerary.id for plan in result.plans]
    conflicts = {plan.itinerary.id: plan.conflicts for plan in result.plans}
    return HTMLResponse(
        templates.get_template("partials/plan_result.html").render(
            request=request,
            plans=[_to_out(it, conflicts[it.id]) for it in _load(session, ids)],
            degraded=result.degraded,
            duration_ms=result.duration_ms,
        )
    )

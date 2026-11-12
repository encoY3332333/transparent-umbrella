"""出行条件校验（UC-02）。

当前阶段不接真实地图服务：城市坐标来自一份小型内置表，
后续把 `_lookup_city()` 替换为 MapAdapter 即可，接口不变。
"""

from __future__ import annotations

from app.core.errors import BusinessError, ErrorCode, FieldError
from app.schemas.condition import (
    BudgetBreakdownHint,
    ConditionValidationOut,
    ResolvedCities,
    ResolvedCity,
    TravelConditionIn,
)

# 只覆盖课程演示会用到的城市；真实版本改由 MapAdapter 提供。
CITY_COORDS: dict[str, tuple[float, float]] = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "南京": (32.0603, 118.7969),
    "苏州": (31.2989, 120.5853),
    "武汉": (30.5928, 114.3055),
    "长沙": (28.2282, 112.9388),
    "成都": (30.5728, 104.0668),
    "重庆": (29.5630, 106.5516),
    "西安": (34.3416, 108.9398),
    "厦门": (24.4798, 118.0894),
    "青岛": (36.0671, 120.3826),
    "昆明": (25.0389, 102.7183),
    "大理": (25.6065, 100.2676),
    "丽江": (26.8550, 100.2278),
    "三亚": (18.2528, 109.5119),
}


def _lookup_city(name: str) -> ResolvedCity | None:
    normalized = name.strip().removesuffix("市")
    coords = CITY_COORDS.get(normalized)
    if coords is None:
        return None
    return ResolvedCity(city=normalized, lat=coords[0], lng=coords[1])


def _fail(code: ErrorCode, field: str, reason: str) -> None:
    raise BusinessError(code=code, details=[FieldError(field=field, reason=reason)])


def validate_condition(payload: TravelConditionIn) -> ConditionValidationOut:
    """按 BR-03 ~ BR-09 校验条件，返回可直接展示的摘要。

    错误码与 docs/api.md 0.3 节、SRS UC-02 对齐；不在 Pydantic 层做范围校验，
    是为了让前端拿到可分支处理的 `CONDITION_*`，而不是笼统的 PARAM_INVALID。
    """

    if payload.endDate < payload.startDate:
        _fail(
            ErrorCode.CONDITION_INVALID_DATE_RANGE,
            "endDate",
            "结束日期不能早于开始日期",
        )

    days = (payload.endDate - payload.startDate).days + 1
    if not 1 <= days <= 15:
        _fail(
            ErrorCode.CONDITION_DURATION_OUT_OF_RANGE,
            "endDate",
            f"duration={days}, allowed=[1,15]",
        )

    if not 500 <= payload.budget <= 200_000:
        _fail(
            ErrorCode.CONDITION_BUDGET_OUT_OF_RANGE,
            "budget",
            f"budget={payload.budget}, allowed=[500,200000]",
        )

    if not 1 <= payload.partySize <= 20:
        _fail(
            ErrorCode.CONDITION_PARTY_SIZE_OUT_OF_RANGE,
            "partySize",
            f"partySize={payload.partySize}, allowed=[1,20]",
        )

    tags = list(dict.fromkeys(payload.preferenceTags))
    if len(tags) > 6:
        _fail(
            ErrorCode.CONDITION_TOO_MANY_TAGS,
            "preferenceTags",
            f"count={len(tags)}, allowed<=6",
        )

    overlap = set(payload.mustVisit) & set(payload.avoidPOI)
    if overlap:
        _fail(
            ErrorCode.CONDITION_MUST_VISIT_CONFLICT,
            "mustVisit",
            f"与 avoidPOI 重复: {sorted(overlap)}",
        )

    origin = _lookup_city(payload.originCity)
    if origin is None:
        _fail(
            ErrorCode.CONDITION_CITY_UNRESOLVED,
            "originCity",
            f"无法解析出发城市: {payload.originCity}",
        )

    dest = _lookup_city(payload.destCity)
    if dest is None:
        _fail(
            ErrorCode.CONDITION_CITY_UNRESOLVED,
            "destCity",
            f"无法解析目的城市: {payload.destCity}",
        )

    per_day = round(payload.budget / days, 2)
    per_person_per_day = round(per_day / payload.partySize, 2)
    warnings: list[str] = []
    if per_person_per_day < 300:
        warnings.append("BUDGET_TIGHT")

    return ConditionValidationOut(
        days=days,
        resolved=ResolvedCities(origin=origin, dest=dest),
        budgetBreakdownHint=BudgetBreakdownHint(
            perDay=per_day,
            perPersonPerDay=per_person_per_day,
        ),
        warnings=warnings,
    )

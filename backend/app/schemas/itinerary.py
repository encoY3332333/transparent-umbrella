"""行程生成接口的请求/响应模型（Issue #4）。

字段名严格对齐 `docs/api.md` 3.1 节（camelCase 出参）。
**入参校验只做「格式与必填」**：预算区间、天数区间这些业务规则归 UC-02（#3），
本 Issue 不重复实现——否则两处阈值迟早不一致，而且前端从哪个入口进来会得到不同结论。
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from app.core.errors import BusinessError, ErrorCode, FieldError


def _camel() -> ConfigDict:
    """统一配置：出参用 camelCase，入参两种写法都收（前端对着 api.md 写 camelCase）。

    故意不接收模型类：在类体里引用 `类名` 会拿到尚未绑定的名字（NameError），
    而写成基类又会让 Pydantic 把配置继承链搞得很难读。
    """
    return ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )


def hhmm(minute: int) -> str:
    """当日分钟数 → `HH:MM`。

    跨零点的活动（夜游 23:00–01:00）`end_minute` 会 ≥ 1440，
    这里按 24 小时取模，避免前端渲染出 `25:30`。
    """
    minute %= 24 * 60
    return f"{minute // 60:02d}:{minute % 60:02d}"


class GenerateRequest(BaseModel):
    """`POST /api/itineraries/generate` 的请求体。

    比 `docs/api.md` 2.1 的出行条件多了 `originCity`——它在生成阶段用不上，
    但用户回看时要知道「从哪出发」，所以允许传、不做校验。
    """

    model_config = _camel()

    dest_city: str = Field(min_length=1, max_length=64, description="目的地城市")
    start_date: date
    end_date: date
    budget: float = Field(gt=0, description="总预算（元）")
    party_size: int = Field(default=1, ge=1, le=20)

    origin_city: str | None = Field(default=None, max_length=64)
    party_type: str | None = None
    preference_tags: list[str] = Field(default_factory=list, max_length=6)
    must_visit: list[int] = Field(default_factory=list)
    # 别名必须手写：`to_camel("avoid_poi")` 得到的是 `avoidPoi`，
    # 而 docs/api.md 2.1 的契约写的是 `avoidPOI`。不指定的话前端照文档传会被
    # `extra="forbid"` 直接打回 `PARAM_INVALID`——字段名对不上的报错极难排查。
    avoid_poi: list[int] = Field(
        default_factory=list, alias="avoidPOI", serialization_alias="avoidPOI"
    )

    variant_count: int = Field(default=2, ge=1, le=3, description="返回方案数 1–3")
    seed: int | None = Field(default=None, description="复现同一套方案用；本 Issue 仅透传")

    @model_validator(mode="after")
    def _check_condition(self) -> GenerateRequest:
        """只做「日期能算天数」这一条，其余阈值交给 UC-02。

        放在这里而不是 service：路由层能拿到「哪个字段错了」，
        抛 `BusinessError` 会带上 `details[].field`，前端可以直接标红对应输入框。
        """
        if self.end_date < self.start_date:
            raise BusinessError(
                code=ErrorCode.CONDITION_INVALID_DATE_RANGE,
                details=[
                    _field(
                        "endDate",
                        f"startDate={self.start_date}, endDate={self.end_date}",
                    )
                ],
            )
        overlap = set(self.must_visit) & set(self.avoid_poi)
        if overlap:
            raise BusinessError(
                code=ErrorCode.CONDITION_MUST_VISIT_CONFLICT,
                details=[_field("mustVisit", f"与 avoidPOI 重复的 id：{sorted(overlap)}")],
            )
        return self

    @property
    def days(self) -> int:
        """天数按「含首尾」算：12-01 到 12-04 是 4 天（与 api.md 示例一致）。"""
        return (self.end_date - self.start_date).days + 1


class ActivityOut(BaseModel):
    """一个活动。时间同时给 `HH:MM` 与分钟数：前端要排序用分钟，要展示用 HH:MM。"""

    model_config = _camel()

    id: int
    poi_id: int
    poi_name: str
    category: str
    start_time: str
    end_time: str
    start_minute: int
    end_minute: int
    cost: float
    travel_minutes: int
    long_transfer: bool
    crowd_index: int | None
    crowd_shifted: bool
    locked: bool
    # 有 ERROR/WARN 冲突指向这一天的这个活动时才会有值
    warnings: list[str] = Field(default_factory=list)


class OutputDay(BaseModel):
    """响应里的一天。与 ORM 的 `ItineraryDay` 分开命名，避免读代码时混淆。"""

    model_config = _camel()

    day_index: int = Field(description="从 0 开始，与 engine 的 day_index 一致")
    day_no: int = Field(description="从 1 开始，前端展示用")
    date: date
    activities: list[ActivityOut]
    free_slot: bool = False
    free_slot_hint: list[str] = Field(default_factory=list)


class ConflictOut(BaseModel):
    """可行性提示。`severity` 决定前端用黄色还是红色角标。"""

    model_config = _camel()

    code: str
    message: str
    severity: str
    day_index: int | None = None


class ItineraryOut(BaseModel):
    model_config = _camel()

    id: int
    title: str
    status: str
    batch_id: str
    city: str
    start_date: date
    day_count: int = Field(description="行程天数；列表用 `days`，两者别混")
    party_size: int
    budget: float
    total_cost: float
    total_minutes: int
    budget_breakdown: dict[str, float]
    reasons: list[dict[str, str]]
    conflicts: list[ConflictOut]
    days: list[OutputDay]


class GenerateResponse(BaseModel):
    """`data` 的形状对齐 api.md 3.1；`strategyVersion` 归 #13，本 Issue 先不填。"""

    model_config = _camel()

    itineraries: list[ItineraryOut]
    degraded: list[str] = Field(default_factory=list)
    duration_ms: int
    strategy_version: int | None = None


def _field(name: str, reason: str) -> FieldError:
    """`BusinessError.details` 的元素，前端据此标红具体输入框。"""
    return FieldError(field=name, reason=reason)

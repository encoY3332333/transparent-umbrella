"""策略参数接口的请求 / 响应模型（Issue #13 / UC-09）。

字段名对齐 `docs/api.md` 10.1–10.3（camelCase 出参）。

**这一层只做「格式与取值区间」校验**；「五项权重之和为 1」（BR-23）放在
`StrategyService.validate_weights()`——它需要报出「当前和是多少」并指向 `weights` 字段，
用 Pydantic 的 validator 写出来的错误信息没法带上求和结果，而 AC-2 要求明确显示当前和。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.strategy import WEIGHT_KEYS


def _camel() -> ConfigDict:
    """与 `schemas/itinerary.py` 同一套配置：出参 camelCase，入参两种写法都收。"""
    return ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )


# 兜底规则名单：权重为 0 时，如果对应兜底也被关掉，该维度就彻底没有信号了，
# 需要用户在页面上二次确认。名字与权重键一致，前端不用再维护一份映射。
FALLBACK_KEYS: tuple[str, ...] = WEIGHT_KEYS

DEFAULT_HOLIDAY_FACTORS: dict[str, float] = {
    "春节": 2.2,
    "国庆": 1.8,
    "普通周末": 1.3,
    "工作日": 1.0,
}

DEFAULT_THRESHOLDS: dict[str, int] = {
    # BR-06：单日游玩时长上限（小时）
    "dailyHours": 10,
    # BR-07：连续步行上限（分钟）
    "maxWalkMinutes": 90,
    # BR-08：超过该分钟数标记为长途转移
    "longTransferMinutes": 60,
    # BR-09：拥挤度 ≥ 该值不在 10:00–15:00 安排
    "crowdAvoidThreshold": 80,
    # 预算降本迭代上限（#7）
    "maxIteration": 30,
}


class WeightsIn(BaseModel):
    """五项权重。区间在这里卡，求和由 service 卡。"""

    model_config = _camel()

    preference: float = Field(ge=0, le=1, description="偏好匹配权重 w_pref")
    weather: float = Field(ge=0, le=1, description="天气适配权重 w_weather")
    crowd: float = Field(ge=0, le=1, description="拥挤度权重 w_crowd")
    travel: float = Field(ge=0, le=1, description="通勤代价权重 w_travel")
    cost: float = Field(ge=0, le=1, description="费用权重 w_cost")

    def as_dict(self) -> dict[str, float]:
        return {key: float(getattr(self, key)) for key in WEIGHT_KEYS}


class ThresholdsIn(BaseModel):
    """规则阈值。全部是正整数，区间按 SRS 的硬约束取。

    这些值**存库但不改 `engine/` 里的常量**：单日时长 / 步行上限 / 长途阈值
    属于 #7 可行性校验的输入，等 #7 合入后由它读本表；本 Issue 先把
    「可配置 + 可版本化」的底座搭好，避免两边同时改同一批常量。
    """

    model_config = _camel()

    daily_hours: int = Field(default=10, ge=1, le=24)
    max_walk_minutes: int = Field(default=90, ge=10, le=600)
    long_transfer_minutes: int = Field(default=60, ge=5, le=600)
    crowd_avoid_threshold: int = Field(default=80, ge=1, le=100)
    max_iteration: int = Field(default=30, ge=1, le=500)

    def as_dict(self) -> dict[str, int]:
        return {
            "dailyHours": self.daily_hours,
            "maxWalkMinutes": self.max_walk_minutes,
            "longTransferMinutes": self.long_transfer_minutes,
            "crowdAvoidThreshold": self.crowd_avoid_threshold,
            "maxIteration": self.max_iteration,
        }


class StrategyPayload(BaseModel):
    """`POST /api/admin/strategies` 的请求体（docs/api.md 10.2）。"""

    model_config = _camel()

    weights: WeightsIn
    holiday_factors: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_HOLIDAY_FACTORS))
    thresholds: ThresholdsIn = Field(default_factory=ThresholdsIn)
    disabled_fallbacks: list[str] = Field(default_factory=list)
    # 权重为 0 且对应兜底关闭时，前端弹二次确认后带 true 重提
    confirm: bool = False


class StrategyVersionOut(BaseModel):
    """一个参数版本。`version=0` 表示「还没发布过任何版本，用的是默认值」。"""

    model_config = _camel()

    version: int
    weights: dict[str, float]
    holiday_factors: dict[str, float]
    thresholds: dict[str, int]
    disabled_fallbacks: list[str]
    note: str = ""
    created_by: str = "system"
    effective_from: datetime | None = None


class StrategyPublishOut(BaseModel):
    """发布结果。

    三种结局共用一个模型，靠 `saved` / `requiresConfirm` 区分：
    - 保存成功：`saved=true`，带上新版本；
    - 需要二次确认：`saved=false, requiresConfirm=true`，`warnings` 里是原因。
    用 200 + 这两个标志，而不是新增两个错误码——`docs/api.md` 0.3 的错误码是
    前后端契约，数量固定为 30，加一个就是破坏性变更。
    """

    model_config = _camel()

    saved: bool
    requires_confirm: bool = False
    warnings: list[str] = Field(default_factory=list)
    strategy: StrategyVersionOut | None = None


class NormalizeIn(BaseModel):
    model_config = _camel()

    weights: WeightsIn


class NormalizeOut(BaseModel):
    model_config = _camel()

    weights: dict[str, float]
    total_before: float


__all__ = [
    "DEFAULT_HOLIDAY_FACTORS",
    "DEFAULT_THRESHOLDS",
    "FALLBACK_KEYS",
    "NormalizeIn",
    "NormalizeOut",
    "StrategyPayload",
    "StrategyPublishOut",
    "StrategyVersionOut",
    "ThresholdsIn",
    "WeightsIn",
]

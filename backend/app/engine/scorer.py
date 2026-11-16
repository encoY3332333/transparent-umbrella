"""综合评分（Issue #6）。

公式严格照 Issue 正文：

    Score(p, d) = w_pref    * PrefMatch(p, tourist)
                + w_weather * WeatherFit(p, d)
                - w_crowd   * CrowdIndex(p, d)
                - w_travel  * TravelMinutes(prev, p) / 30
                - w_cost    * Price(p) / Budget

约束 sum(w_*) = 1，w_* ∈ [0, 1]。默认权重（问卷 Q5 归一化取整）：
pref=0.10  weather=0.25  crowd=0.23  travel=0.14  cost=0.28。

**纯净层**：不 import adapters / models / SQLAlchemy，纯函数、可脱离数据库单测。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Final

from app.engine.selector import Candidate, Poi

# 天气分级。数值越大越适合出行；`WeatherFit` 直接用它。
# 暴雨/大风/高温由 `is_weather_hostile()` 判定为 BR-08 的禁排情形。
WEATHER_CLEAR: Final = "CLEAR"
WEATHER_CLOUDY: Final = "CLOUDY"
WEATHER_OVERCAST: Final = "OVERCAST"
WEATHER_RAIN: Final = "RAIN"
WEATHER_STORM: Final = "STORM"  # 暴雨
WEATHER_WIND: Final = "WIND"  # 大风 ≥6 级
WEATHER_HEAT: Final = "HEAT"  # 高温 ≥38℃

HOSTILE_WEATHERS: Final[frozenset[str]] = frozenset({WEATHER_STORM, WEATHER_WIND, WEATHER_HEAT})

# 户外类 POI 的 category 取值（与 seed/pois.json 及 SRS 数据字典一致）
OUTDOOR_CATEGORIES: Final[frozenset[str]] = frozenset({"OUTDOOR", "NATURE", "SCENIC"})

# WeatherFit 取值表。CLEAR 满分，STORM 给负分——
# Issue 要求「对暴雨/大风/高温返回 0 或负值」，给负数是让禁排之外的情形也明显靠后。
WEATHER_FIT: Final[Mapping[str, float]] = {
    WEATHER_CLEAR: 1.00,
    WEATHER_CLOUDY: 0.85,
    WEATHER_OVERCAST: 0.75,
    WEATHER_RAIN: 0.35,
    WEATHER_STORM: -1.00,
    WEATHER_WIND: -0.60,
    WEATHER_HEAT: -0.40,
}

# 未知天气不惩罚也不奖励：中性 0.5，并让调用方在 degraded[] 里标注
WEATHER_FIT_UNKNOWN: Final = 0.5


def is_weather_hostile(weather: str | None) -> bool:
    """BR-08：暴雨 / 大风（≥6 级）/ 高温（≥38℃）判定。"""
    return weather in HOSTILE_WEATHERS


def is_outdoor(poi: Poi) -> bool:
    """POI 是否为户外类；BR-08 禁排判定用。"""
    return poi.category.upper() in OUTDOOR_CATEGORIES


@dataclass(frozen=True)
class Weights:
    """五项评分权重。`__post_init__` 里强制 BR-23（和为 1）。"""

    pref: float = 0.10
    weather: float = 0.25
    crowd: float = 0.23
    travel: float = 0.14
    cost: float = 0.28

    def __post_init__(self) -> None:
        for name in ("pref", "weather", "crowd", "travel", "cost"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"权重 {name}={value} 必须在 [0,1] 内")
        total = self.pref + self.weather + self.crowd + self.travel + self.cost
        # BR-23：误差 < 0.001，与 Settings 的校验口径保持一致
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"五项权重之和必须为 1，当前 {total:.4f}")

    def perturbed(self, name: str, delta: float) -> Weights:
        """扰动某一项权重并归一化，用于生成差异化方案（Issue #6 第 5 条任务）。

        直接把某权重加减 delta 会让和偏离 1，所以按比例缩放其余四项。
        """
        if name not in ("pref", "weather", "crowd", "travel", "cost"):
            raise ValueError(f"未知权重名: {name}")
        raw = {
            "pref": self.pref,
            "weather": self.weather,
            "crowd": self.crowd,
            "travel": self.travel,
            "cost": self.cost,
        }
        target = min(1.0, max(0.0, raw[name] + delta))
        raw[name] = target
        others = [k for k in raw if k != name]
        remaining = 1.0 - target
        current_others = sum(raw[k] for k in others)
        if current_others <= 1e-9:
            # 其余四项全为 0 时只能平均分
            for k in others:
                raw[k] = remaining / len(others)
        else:
            for k in others:
                raw[k] = raw[k] / current_others * remaining
        return Weights(**raw)


@dataclass(frozen=True)
class TouristProfile:
    """评分需要的游客侧输入。

    `preference_tags` 来自 UC-02 的偏好标签；`budget` 是总预算，
    用于把门票价格归一化到 [0,1]。
    """

    preference_tags: frozenset[str] = frozenset()
    budget: float = 1000.0


def pref_match(poi: Poi, tourist: TouristProfile) -> float:
    """偏好匹配度 ∈ [0,1]：命中标签数 / 用户标签总数。

    用户没选标签时返回中性 0.5——不选偏好是合法输入（UC-02 允许空），
    此时用 0 会惩罚所有 POI，让 w_pref 那一项失去区分意义。
    """
    if not tourist.preference_tags:
        return 0.5
    hit = len(set(poi.tags) & tourist.preference_tags)
    return hit / len(tourist.preference_tags)


def weather_fit(poi: Poi, weather: str | None) -> float:
    """天气适配度。

    室内 POI 几乎不受天气影响（暴雨也只是少 10 分），
    户外 POI 完全按天气表打分——这样暴雨下室内会自然胜出。
    """
    base = WEATHER_FIT.get(weather or "", WEATHER_FIT_UNKNOWN)
    if is_outdoor(poi):
        return base
    # 室内：坏天气的影响削弱到 1/5，好天气不打折
    return 1.0 - (1.0 - base) / 5.0 if base < 1.0 else base


def travel_cost(prev: Poi | None, poi: Poi, minutes: float) -> float:
    """通勤惩罚项，已按公式归一化（min / 30）。

    `prev` 为 None 表示当天第一个活动，没有通勤成本。
    """
    if prev is None:
        return 0.0
    return max(minutes, 0.0) / 30.0


def cost_ratio(poi: Poi, budget: float) -> float:
    """门票占预算比例，已截断到 [0,1]。

    预算为 0（理论上被 UC-02 拦住，这里仍要防）时返回 1.0，
    让所有收费 POI 都拿到最差分，避免 ZeroDivisionError。
    """
    if budget <= 0:
        return 1.0
    return min(max(poi.price / budget, 0.0), 1.0)


def crowd_penalty(crowd_index: int | None) -> float:
    """拥挤度惩罚项 ∈ [0,1]。

    数据缺失（None）时给中性 0.5 而不是 0：给 0 等于凭空奖励「没人流数据」的 POI，
    而那些往往是数据源没覆盖到的小众点，不该因此排到最前面。
    """
    if crowd_index is None:
        return 0.5
    return min(max(crowd_index, 0), 100) / 100.0


@dataclass(frozen=True)
class ScoreBreakdown:
    """单次评分的明细，供推荐理由生成与调试使用。"""

    total: float
    pref: float
    weather: float
    crowd: float
    travel: float
    cost: float


class Scorer:
    """把五项因子加权成总分。无状态，可安全复用。"""

    def __init__(self, weights: Weights | None = None) -> None:
        self.weights = weights or Weights()

    def score(
        self,
        candidate: Candidate,
        *,
        tourist: TouristProfile,
        weather: str | None,
        prev: Poi | None = None,
        travel_minutes: float = 0.0,
    ) -> ScoreBreakdown:
        w = self.weights
        poi = candidate.poi

        p = pref_match(poi, tourist)
        wt = weather_fit(poi, weather)
        cr = crowd_penalty(candidate.crowd_index)
        tv = travel_cost(prev, poi, travel_minutes)
        cs = cost_ratio(poi, tourist.budget)

        total = w.pref * p + w.weather * wt - w.crowd * cr - w.travel * tv - w.cost * cs
        return ScoreBreakdown(total=total, pref=p, weather=wt, crowd=cr, travel=tv, cost=cs)

    def total(
        self,
        candidate: Candidate,
        *,
        tourist: TouristProfile,
        weather: str | None,
        prev: Poi | None = None,
        travel_minutes: float = 0.0,
    ) -> float:
        return self.score(
            candidate,
            tourist=tourist,
            weather=weather,
            prev=prev,
            travel_minutes=travel_minutes,
        ).total


def day_weather(weather_by_day: Mapping[date, str], day: date) -> str | None:
    """取某天的天气；缺数据返回 None，由调用方决定是否降级。"""
    return weather_by_day.get(day)

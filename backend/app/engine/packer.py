"""时间轴装箱与硬约束（Issue #6）。

把候选 POI 按评分贪心装进每天的行程，逐日输出 `DayPlan`。

硬约束（BR-06 ~ BR-09）：
- BR-06 单日活动总时长（含通勤）≤ 10 小时；连续步行 ≤ 90 分钟；
- BR-07 相邻活动通勤 > 60 分钟时该活动标 `long_transfer=True`；
- BR-08 暴雨 / 大风（≥6 级）/ 高温（≥38℃）不得安排户外类 POI；
- BR-09 拥挤度 ≥ 80 的 POI 不得安排在 10:00–15:00。

三个「时段常量」集中放在本模块顶部，改作息只改一处：
用餐 11:30–13:00、17:30–19:00，每 90 分钟步行强制休息 15 分钟。

**纯净层**：不 import adapters / models / SQLAlchemy。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, time, timedelta

from app.engine.scorer import (
    OUTDOOR_CATEGORIES,
    Scorer,
    TouristProfile,
    Weights,
    is_outdoor,
    is_weather_hostile,
)
from app.engine.selector import Candidate, Poi

# ---------------------------------------------------------------- 时段常量
LUNCH_START: time = time(11, 30)
LUNCH_END: time = time(13, 0)
DINNER_START: time = time(17, 30)
DINNER_END: time = time(19, 0)
LUNCH_MINUTES = 60
DINNER_MINUTES = 60

# BR-06
DAILY_LIMIT_MINUTES = 10 * 60
CONTINUOUS_WALK_LIMIT = 90
REST_MINUTES = 15

# BR-07
LONG_TRANSFER_MINUTES = 60

# BR-09
CROWD_BUSY_THRESHOLD = 80
CROWD_BUSY_WINDOW_START = time(10, 0)
CROWD_BUSY_WINDOW_END = time(15, 0)

# 参观一个 POI 的默认时长。真实版本应按 POI 热度/面积分档，
# 课程阶段用 90 分钟统一，注释清楚即可，不要假装有数据支撑。
DEFAULT_VISIT_MINUTES = 90
MIN_ACTIVITIES_PER_DAY = 2


class PackError(Exception):
    """装箱无法满足硬约束。"""


@dataclass(frozen=True)
class Activity:
    """行程中的一个活动（不含用餐与休息，那些只记账不产出 Activity）。"""

    poi_id: int
    name: str
    category: str
    start: time
    end: time
    price: float
    crowd_index: int | None
    travel_minutes: int = 0
    long_transfer: bool = False
    score: float = 0.0
    crowd_shifted: bool = False

    @property
    def duration_minutes(self) -> int:
        return _minutes(self.end) - _minutes(self.start)


@dataclass
class DayPlan:
    """一天的行程。"""

    day: date
    activities: list[Activity] = field(default_factory=list)
    free_slot: bool = False
    free_slot_hint: list[str] = field(default_factory=list)
    total_minutes: int = 0

    @property
    def activity_count(self) -> int:
        return len(self.activities)

    @property
    def cost(self) -> float:
        return sum(a.price for a in self.activities)


@dataclass(frozen=True)
class PlanResult:
    """一套完整方案。"""

    days: tuple[DayPlan, ...]
    reasons: tuple[str, ...]
    weights: Weights
    poi_ids: frozenset[int]

    @property
    def total_cost(self) -> float:
        return sum(d.cost for d in self.days)


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _time_of(minutes: int) -> time:
    """把分钟数转回 time；超过 24 点则截断到 23:59（BR-06 会先拦住这种溢出）。"""
    minutes = max(0, min(minutes, 24 * 60 - 1))
    return time(minutes // 60, minutes % 60)


def _overlaps(start: int, end: int, win_start: time, win_end: time) -> bool:
    ws, we = _minutes(win_start), _minutes(win_end)
    return start < we and end > ws


def _in_busy_window(start: int, end: int) -> bool:
    return _overlaps(start, end, CROWD_BUSY_WINDOW_START, CROWD_BUSY_WINDOW_END)


def weather_for(weather_by_day: Mapping[date | None, str], day: date) -> str | None:
    """取某天天气：先精确匹配，再退到 `None` 键的默认值。

    两者都没有返回 `None`。此时 BR-08 **不放行**户外——理由见 `_plan_one_day`
    对 `weather is None` 的处理：宁可少排，也不能拿「不知道天气」当晴天用。
    """
    if day in weather_by_day:
        return weather_by_day[day]
    return weather_by_day.get(None)


@dataclass(frozen=True)
class _Slot:
    """试排产生的一个可行时段（内部用，不对外导出）。"""

    cand: Candidate
    arrive: int
    end: int
    travel: int
    shifted: bool
    walk_after: int
    score: float


class Packer:
    """按天贪心装箱。

    每个候选按「当前时间点」重新评分（因为通勤项依赖上一个 POI），
    取分最高且能通过硬约束的那个放进去；放不进去就试下一个。
    """

    def __init__(
        self,
        scorer: Scorer | None = None,
        *,
        visit_minutes: int = DEFAULT_VISIT_MINUTES,
    ) -> None:
        self.scorer = scorer or Scorer()
        self.visit_minutes = visit_minutes

    # ------------------------------------------------------------ 对外入口
    def plan(
        self,
        *,
        start_date: date,
        days: int,
        candidates: Sequence[Candidate],
        tourist: TouristProfile,
        weather_by_day: Mapping[date | None, str],
        travel_minutes: Mapping[tuple[int, int], int] | None = None,
        day_start: time = time(9, 0),
    ) -> PlanResult:
        """生成一套方案。

        `weather_by_day` 支持用 `None` 作为「其余各天的默认天气」。
        没有默认值又查不到某天的天气时，BR-08 不会因为「不知道天气」而放行户外——
        见 `weather_for()`。
        """
        if days < 1:
            raise ValueError("days 必须 >= 1")

        matrix = travel_minutes or {}
        remaining = list(candidates)
        day_plans: list[DayPlan] = []

        for offset in range(days):
            current_day = start_date + timedelta(days=offset)
            weather = weather_for(weather_by_day, current_day)
            plan = self._plan_one_day(
                day=current_day,
                candidates=remaining,
                tourist=tourist,
                weather=weather,
                matrix=matrix,
                day_start=day_start,
            )
            day_plans.append(plan)
            # 已排入的 POI 从池子里移除，避免同一次行程内重复安排
            used = {a.poi_id for a in plan.activities}
            remaining = [c for c in remaining if c.poi.id not in used]

        reasons = build_reasons(day_plans, weather_by_day, self.scorer.weights)
        poi_ids = frozenset(a.poi_id for d in day_plans for a in d.activities)
        return PlanResult(
            days=tuple(day_plans),
            reasons=reasons,
            weights=self.scorer.weights,
            poi_ids=poi_ids,
        )

    # ------------------------------------------------------------ 单日
    def _plan_one_day(
        self,
        *,
        day: date,
        candidates: Sequence[Candidate],
        tourist: TouristProfile,
        weather: str | None,
        matrix: Mapping[tuple[int, int], int],
        day_start: time,
    ) -> DayPlan:
        plan = DayPlan(day=day)
        cursor = _minutes(day_start)
        day_limit = _minutes(day_start) + DAILY_LIMIT_MINUTES
        prev: Poi | None = None
        walking_since_rest = 0
        pool = list(candidates)

        while cursor < day_limit:
            cursor = self._skip_meal(cursor)
            if cursor >= day_limit:
                break

            best: _Slot | None = None
            for cand in pool:
                slot = self._fit(
                    cand,
                    cursor=cursor,
                    prev=prev,
                    weather=weather,
                    matrix=matrix,
                    day_limit=day_limit,
                    walking_since_rest=walking_since_rest,
                )
                if slot is None:
                    continue

                breakdown = self.scorer.score(
                    cand,
                    tourist=tourist,
                    weather=weather,
                    prev=prev,
                    travel_minutes=slot.travel,
                )
                if best is None or breakdown.total > best.score:
                    best = replace(slot, score=breakdown.total)

            if best is None:
                break

            # 推到开放时间 / 用餐结束 / 拥挤错峰之后，中间的空档算自由时间，
            # 但仍然不能超过单日上限。
            if best.arrive >= day_limit:
                break

            poi = best.cand.poi
            arrive, end = best.arrive, best.end

            plan.activities.append(
                Activity(
                    poi_id=poi.id,
                    name=poi.name,
                    category=poi.category,
                    start=_time_of(arrive),
                    end=_time_of(end),
                    price=poi.price,
                    crowd_index=best.cand.crowd_index,
                    travel_minutes=best.travel,
                    long_transfer=best.travel > LONG_TRANSFER_MINUTES,
                    score=round(best.score, 4),
                    crowd_shifted=best.shifted,
                )
            )

            needs_rest = best.walk_after > CONTINUOUS_WALK_LIMIT
            walking_since_rest = 0 if needs_rest else best.walk_after
            cursor = end + (REST_MINUTES if needs_rest else 0)
            prev = poi
            pool.remove(best.cand)

        plan.total_minutes = cursor - _minutes(day_start)
        if plan.activity_count < MIN_ACTIVITIES_PER_DAY:
            # 活动不足：保留已排的，并标记自由时段（Issue #6 验收标准第 6 条）
            plan.free_slot = True
            plan.free_slot_hint = [f"{c.poi.name}（{c.poi.category}）" for c in candidates[:3]]
        return plan

    # ------------------------------------------------------------ 单个候选试排
    def _fit(
        self,
        cand: Candidate,
        *,
        cursor: int,
        prev: Poi | None,
        weather: str | None,
        matrix: Mapping[tuple[int, int], int],
        day_limit: int,
        walking_since_rest: int,
    ) -> _Slot | None:
        """尝试把候选放进从 `cursor` 开始的这一天。

        返回 `None` 表示这一天放不下（跳过），否则返回实际可行的时段。
        关键点：遇到用餐窗口 / 拥挤高峰 / 还没开门时**顺延**而不是放弃，
        顺延后仍然放不下才返回 `None`——否则 09:00 开始第一个 90 分钟的活动
        必然撞上 11:30 的午休，一整天就再也排不进第二个活动了。
        """
        poi = cand.poi

        # BR-08：恶劣天气禁排户外。
        # 天气未知（None）时同样禁排户外——天气预报拿不到是数据源降级，
        # 不能当作晴天处理，否则「查不到天气」的城市会被排进一整天的户外行程。
        if is_outdoor(poi) and (weather is None or is_weather_hostile(weather)):
            return None

        travel = self._travel_minutes(matrix, prev, poi)
        arrive = max(cursor + travel, _minutes(_parse_time(poi.open_time)))
        close_m = _minutes(_parse_time(poi.close_time))

        # 顺延循环：三个可能把活动往后推的原因，逐个处理，直到稳定
        for _ in range(4):
            end = arrive + self.visit_minutes

            # 用餐时段不能被活动跨过（否则「边逛边吃」不符合 BR-06 的记账口径）
            pushed_past_meal = self._after_meal(arrive, end)
            if pushed_past_meal is not None:
                arrive = pushed_past_meal
                continue

            # BR-09：高拥挤度错峰。落在 10:00–15:00 就推到 15:00 之后
            if (
                cand.crowd_index is not None
                and cand.crowd_index >= CROWD_BUSY_THRESHOLD
                and _in_busy_window(arrive, end)
            ):
                arrive = max(arrive, _minutes(CROWD_BUSY_WINDOW_END))
                continue

            break
        else:  # pragma: no cover - 顺延一定会在 4 次内稳定
            return None

        end = arrive + self.visit_minutes
        if end > close_m:
            return None
        if arrive + self.visit_minutes > day_limit:
            return None

        # BR-06：连续步行（不含休息）超过 90 分钟要插休息，休息会占时间
        walk_after = walking_since_rest + (end - arrive) + travel
        extra_rest = REST_MINUTES if walk_after > CONTINUOUS_WALK_LIMIT else 0
        if end + extra_rest > day_limit:
            return None

        return _Slot(
            cand=cand,
            arrive=arrive,
            end=end,
            travel=travel,
            shifted=arrive > cursor + travel,
            walk_after=walk_after,
            score=0.0,
        )

    # ------------------------------------------------------------ 辅助
    @staticmethod
    def _travel_minutes(matrix: Mapping[tuple[int, int], int], prev: Poi | None, poi: Poi) -> int:
        """通勤时长。矩阵缺项时给保守估计，而不是 0——
        给 0 会让「没数据」的 POI 显得很近，把距离约束架空。"""
        if prev is None or prev.id == poi.id:
            return 0
        return int(matrix.get((prev.id, poi.id), 30))

    @staticmethod
    def _after_meal(start: int, end: int) -> int | None:
        """活动若跨过用餐窗口，返回「吃完再开始」的时刻；不跨则返回 None。"""
        for ws, we in ((LUNCH_START, LUNCH_END), (DINNER_START, DINNER_END)):
            if _overlaps(start, end, ws, we):
                return _minutes(we)
        return None

    @staticmethod
    def _skip_meal(cursor: int) -> int:
        """若游标落在用餐窗口内，推过窗口末尾（等价于「去吃午饭」）。"""
        if _minutes(LUNCH_START) <= cursor < _minutes(LUNCH_END):
            return max(cursor, _minutes(LUNCH_START) + LUNCH_MINUTES)
        if _minutes(DINNER_START) <= cursor < _minutes(DINNER_END):
            return max(cursor, _minutes(DINNER_START) + DINNER_MINUTES)
        return cursor


def _parse_time(raw: str) -> time:
    """``"09:00"`` -> ``time(9, 0)``。"""
    hour, minute = raw.split(":")[:2]
    return time(int(hour), int(minute))


def build_reasons(
    day_plans: Iterable[DayPlan],
    weather_by_day: Mapping[date | None, str],
    weights: Weights,
) -> tuple[str, ...]:
    """生成至少 3 条推荐理由，并附数据来源标注（Issue #6 任务清单第 6 条）。"""
    plans = list(day_plans)
    reasons: list[str] = []

    hostile_days = [d for d in plans if is_weather_hostile(weather_for(weather_by_day, d.day))]
    unknown_days = [
        d
        for d in plans
        if weather_for(weather_by_day, d.day) is None and d not in hostile_days and d.activity_count
    ]
    if hostile_days:
        names = "、".join(d.day.strftime("%m-%d") for d in hostile_days)
        reasons.append(f"{names} 天气不适宜户外，已全部改排室内景点（依据：天气预报 BR-08）")
    if unknown_days:
        names = "、".join(d.day.strftime("%m-%d") for d in unknown_days)
        reasons.append(f"{names} 未取到天气预报，按保守口径只排室内景点（依据：BR-08 降级策略）")

    busy = [a for d in plans for a in d.activities if a.crowd_shifted]
    if busy:
        preview = "、".join(a.name for a in busy[:2])
        reasons.append(f"{preview} 等人流密集景区已避开 10:00–15:00 高峰（依据：历史人流量 BR-09）")

    long_legs = [a for d in plans for a in d.activities if a.long_transfer]
    if long_legs:
        preview = "、".join(f"{a.name}（{a.travel_minutes} 分钟）" for a in long_legs[:2])
        reasons.append(f"已标注长距离通勤：{preview}（依据：实时路况 BR-07）")

    order = sorted(
        (
            {"pref": "偏好", "weather": "天气", "crowd": "人流", "travel": "通勤", "cost": "预算"}
        ).items(),
        key=lambda kv: -getattr(weights, kv[0]),
    )
    top2 = "、".join(f"{label}({getattr(weights, key):.2f})" for key, label in order[:2])
    reasons.append(f"本方案的权重侧重：{top2}（依据：问卷 Q5 的约束重要性排序，BR-23）")

    total_activities = sum(d.activity_count for d in plans)
    free_days = [d for d in plans if d.free_slot]
    if free_days:
        names = "、".join(d.day.strftime("%m-%d") for d in free_days)
        reasons.append(f"{names} 可安排景点不足，已预留自由活动时段（依据：候选池规模）")

    if total_activities:
        reasons.append(
            f"共安排 {total_activities} 个活动，日均 {total_activities / len(plans):.1f} 个"
        )

    # 兜底：至少 3 条
    while len(reasons) < 3:
        reasons.append("行程已按单日 10 小时上限与用餐时段约束校验通过（依据：BR-06）")
    return tuple(reasons[:6])


__all__ = [
    "OUTDOOR_CATEGORIES",
    "Activity",
    "DayPlan",
    "PackError",
    "Packer",
    "PlanResult",
    "build_reasons",
    "is_outdoor",
]

"""Issue #6 排程引擎测试。

覆盖 Issue 正文「测试」清单的六类场景：
1. 正常排程
2. 暴雨禁排户外
3. 高拥挤度错峰
4. 通勤超 60 分钟标注
5. 单日超 10 小时
6. 活动不足插入自由时段

另附评分公式、权重校验、方案差异化、推荐理由的测试。
"""

from __future__ import annotations

from datetime import date, time

import pytest

from app.engine.packer import (
    DEFAULT_VISIT_MINUTES,
    LUNCH_END,
    LUNCH_START,
    Activity,
    DayPlan,
    Packer,
    build_reasons,
)
from app.engine.scorer import (
    Scorer,
    TouristProfile,
    Weights,
    cost_ratio,
    crowd_penalty,
    is_outdoor,
    is_weather_hostile,
    pref_match,
    weather_fit,
)
from app.engine.selector import Candidate, Poi
from app.engine.strategy_engine import (
    MAX_OVERLAP_RATIO,
    PlanRequest,
    StrategyEngine,
    overlap_ratio,
)
from app.engine.travel import TravelMatrix, build_matrix

DAY = date(2026, 12, 1)


def make_poi(
    poi_id: int,
    *,
    category: str = "INDOOR",
    price: float = 0.0,
    tags: tuple[str, ...] = ("人文历史",),
    open_time: str = "09:00",
    close_time: str = "18:00",
    capacity: int = 5000,
) -> Poi:
    return Poi(
        id=poi_id,
        name=f"景点{poi_id}",
        city="西安",
        category=category,
        lat=34.2 + poi_id * 0.001,
        lng=108.9 + poi_id * 0.001,
        open_time=open_time,
        close_time=close_time,
        price=price,
        capacity=capacity,
        tags=tags,
        status="PUBLISHED",
    )


def cand(poi: Poi, crowd: int | None = None) -> Candidate:
    return Candidate(poi=poi, crowd_index=crowd)


def tourist(tags: tuple[str, ...] = ("人文历史",), budget: float = 6000.0) -> TouristProfile:
    return TouristProfile(preference_tags=frozenset(tags), budget=budget)


# ======================================================================
# 1. 评分公式
# ======================================================================
class TestScorer:
    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="之和必须为 1"):
            Weights(pref=0.5, weather=0.5, crowd=0.5, travel=0.5, cost=0.5)

    def test_weights_must_be_in_range(self) -> None:
        with pytest.raises(ValueError, match=r"必须在 \[0,1\] 内"):
            Weights(pref=1.5, weather=-0.1, crowd=0.23, travel=0.14, cost=0.28)

    def test_default_weights_match_issue(self) -> None:
        w = Weights()
        assert (w.pref, w.weather, w.crowd, w.travel, w.cost) == (0.10, 0.25, 0.23, 0.14, 0.28)
        assert abs(sum((w.pref, w.weather, w.crowd, w.travel, w.cost)) - 1.0) < 1e-9

    def test_perturb_keeps_sum_one(self) -> None:
        for name in ("pref", "weather", "crowd", "travel", "cost"):
            w = Weights().perturbed(name, 0.12)
            total = w.pref + w.weather + w.crowd + w.travel + w.cost
            assert abs(total - 1.0) < 1e-9, name

    def test_score_formula_is_exact(self) -> None:
        """手算一遍，确认加权方式与 Issue 公式逐项一致。"""
        w = Weights()
        poi = make_poi(1, category="INDOOR", price=600.0, tags=("人文历史", "美食"))
        c = cand(poi, crowd=40)
        t = tourist(("人文历史", "美食"), budget=6000.0)
        prev = make_poi(2)

        got = Scorer(w).score(c, tourist=t, weather="CLEAR", prev=prev, travel_minutes=45)

        pref = 2 / 2  # 命中 2 个标签 / 共 2 个标签
        weather = 1.0  # CLEAR
        crowd = 40 / 100
        travel = 45 / 30
        cost = 600 / 6000
        expected = (
            w.pref * pref
            + w.weather * weather
            - w.crowd * crowd
            - w.travel * travel
            - w.cost * cost
        )
        assert got.pref == pytest.approx(pref)
        assert got.weather == pytest.approx(weather)
        assert got.crowd == pytest.approx(crowd)
        assert got.travel == pytest.approx(travel)
        assert got.cost == pytest.approx(cost)
        assert got.total == pytest.approx(expected)

    def test_first_activity_has_no_travel_penalty(self) -> None:
        poi = make_poi(1)
        c = cand(poi, crowd=0)
        s = Scorer()
        with_prev = s.total(
            c, tourist=tourist(), weather="CLEAR", prev=make_poi(9), travel_minutes=90
        )
        no_prev = s.total(c, tourist=tourist(), weather="CLEAR", prev=None)
        assert no_prev > with_prev

    def test_pref_match_neutral_when_no_tags(self) -> None:
        """用户没选偏好是合法输入，此时应给中性分而不是 0。"""
        assert pref_match(make_poi(1), TouristProfile(preference_tags=frozenset())) == 0.5

    def test_pref_match_full_and_zero(self) -> None:
        t = tourist(("人文历史", "美食"))
        assert pref_match(make_poi(1, tags=("人文历史", "美食")), t) == 1.0
        assert pref_match(make_poi(2, tags=("自然风光",)), t) == 0.0

    def test_weather_fit_hostile_is_non_positive_for_outdoor(self) -> None:
        """Issue 要求：暴雨/大风/高温对户外返回 0 或负值。"""
        outdoor = make_poi(1, category="OUTDOOR")
        for weather in ("STORM", "WIND", "HEAT"):
            assert weather_fit(outdoor, weather) <= 0.0, weather

    def test_weather_fit_indoor_less_affected(self) -> None:
        indoor = make_poi(1, category="INDOOR")
        outdoor = make_poi(2, category="OUTDOOR")
        assert weather_fit(indoor, "STORM") > weather_fit(outdoor, "STORM")

    def test_weather_fit_unknown_is_neutral(self) -> None:
        """室内点在天气未知时只被轻微打折（好天气不打折、坏天气削到 1/5）。

        未知天气的「中性值」是给**户外点**用的；室内点走的是削弱分支，
        所以 0.5 会被抬到 0.9，这是有意的：室内本来就不靠天气加分。
        """
        assert weather_fit(make_poi(1, category="OUTDOOR"), None) == pytest.approx(0.5)
        assert weather_fit(make_poi(2, category="INDOOR"), None) == pytest.approx(0.9)

    def test_crowd_penalty_none_is_neutral_not_zero(self) -> None:
        """数据缺失给中性 0.5，不能给 0——否则等于奖励没有数据的 POI。"""
        assert crowd_penalty(None) == 0.5

    def test_crowd_penalty_clamped(self) -> None:
        assert crowd_penalty(150) == 1.0
        assert crowd_penalty(-20) == 0.0

    def test_cost_ratio_clamped(self) -> None:
        poi = make_poi(1, price=9000.0)
        assert cost_ratio(poi, 6000.0) == 1.0
        assert cost_ratio(make_poi(2, price=0.0), 6000.0) == 0.0

    def test_cost_ratio_zero_budget_no_div_by_zero(self) -> None:
        assert cost_ratio(make_poi(1, price=100.0), 0.0) == 1.0

    def test_is_weather_hostile(self) -> None:
        assert is_weather_hostile("STORM")
        assert is_weather_hostile("WIND")
        assert is_weather_hostile("HEAT")
        assert not is_weather_hostile("CLEAR")
        assert not is_weather_hostile(None)

    def test_is_outdoor(self) -> None:
        assert is_outdoor(make_poi(1, category="OUTDOOR"))
        assert is_outdoor(make_poi(2, category="NATURE"))
        assert not is_outdoor(make_poi(3, category="INDOOR"))


# ======================================================================
# 2. 正常排程
# ======================================================================
class TestNormalPlan:
    def test_activities_do_not_overlap_and_are_ordered(self) -> None:
        pois = [make_poi(i) for i in range(1, 9)]
        candidates = [cand(p, crowd=10) for p in pois]
        result = Packer().plan(
            start_date=DAY,
            days=2,
            candidates=candidates,
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )

        for day_plan in result.days:
            previous_end = -1
            for act in day_plan.activities:
                start = act.start.hour * 60 + act.start.minute
                end = act.end.hour * 60 + act.end.minute
                assert start >= previous_end, f"{act.name} 与前一个活动时间重叠"
                assert end > start
                previous_end = end

    def test_travel_time_is_counted_between_activities(self) -> None:
        """相邻活动之间必须留出通勤时间。"""
        pois = [make_poi(i) for i in (1, 2)]
        candidates = [cand(p, crowd=0) for p in pois]
        matrix = {(1, 2): 40, (2, 1): 40}
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=candidates,
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
            travel_minutes=matrix,
        )

        acts = result.days[0].activities
        if len(acts) >= 2:
            first_end = acts[0].end.hour * 60 + acts[0].end.minute
            second_start = acts[1].start.hour * 60 + acts[1].start.minute
            assert second_start - first_end >= 40

    def test_activity_within_open_hours(self) -> None:
        poi = make_poi(1, open_time="14:00", close_time="16:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(poi, crowd=0)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        acts = result.days[0].activities
        assert len(acts) == 1
        assert acts[0].start >= time(14, 0)
        assert acts[0].end <= time(16, 0)

    def test_closed_poi_is_skipped(self) -> None:
        """整天关门的 POI 不能被排进来。"""
        poi = make_poi(1, open_time="20:00", close_time="21:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(poi, crowd=0)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        assert result.days[0].activity_count == 0
        assert result.days[0].free_slot is True

    def test_no_activity_crosses_meal_window(self) -> None:
        """用餐时段不能被活动跨过。"""
        pois = [make_poi(i) for i in range(1, 10)]
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(p, crowd=0) for p in pois],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        lunch_start = LUNCH_START.hour * 60 + LUNCH_START.minute
        lunch_end = LUNCH_END.hour * 60 + LUNCH_END.minute
        for act in result.days[0].activities:
            start = act.start.hour * 60 + act.start.minute
            end = act.end.hour * 60 + act.end.minute
            assert not (start < lunch_end and end > lunch_start), f"{act.name} 跨过了午餐时段"

    def test_same_poi_not_repeated_across_days(self) -> None:
        pois = [make_poi(i) for i in range(1, 5)]
        result = Packer().plan(
            start_date=DAY,
            days=3,
            candidates=[cand(p, crowd=0) for p in pois],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        ids = [a.poi_id for d in result.days for a in d.activities]
        assert len(ids) == len(set(ids)), "同一次行程内出现了重复景点"


# ======================================================================
# 3. BR-08 暴雨禁排户外
# ======================================================================
class TestHostileWeather:
    @pytest.mark.parametrize("weather", ["STORM", "WIND", "HEAT"])
    def test_no_outdoor_poi_under_hostile_weather(self, weather: str) -> None:
        """验收标准：暴雨/大风/高温输入下，方案中完全不出现户外 POI。

        `None` 键是「其余各天的默认天气」——多日行程必须每天都能查到天气，
        否则某一天拿不到天气就等于给户外开了后门（见下面的回归测试）。
        """
        pois = [
            make_poi(1, category="OUTDOOR"),
            make_poi(2, category="NATURE"),
            make_poi(3, category="INDOOR"),
            make_poi(4, category="INDOOR"),
        ]
        result = Packer().plan(
            start_date=DAY,
            days=5,
            candidates=[cand(p, crowd=0) for p in pois],
            tourist=tourist(),
            weather_by_day={DAY: weather, None: weather},
        )
        categories = {a.category for d in result.days for a in d.activities}
        assert "OUTDOOR" not in categories
        assert "NATURE" not in categories

    def test_missing_weather_on_later_day_still_blocks_outdoor(self) -> None:
        """回归：只有第一天有天气时，第二天不能因为「天气未知」把户外排进去。

        修复前 `weather_by_day.get(day)` 对第二天返回 None，
        `is_weather_hostile(None)` 为 False，户外 POI 直接绕过 BR-08。
        """
        pois = [
            make_poi(1, category="OUTDOOR"),
            make_poi(2, category="NATURE"),
            make_poi(3, category="INDOOR"),
        ]
        result = Packer().plan(
            start_date=DAY,
            days=2,
            candidates=[cand(p, crowd=0) for p in pois],
            tourist=tourist(),
            weather_by_day={},  # 一条天气都没有
        )
        categories = {a.category for d in result.days for a in d.activities}
        assert categories <= {"INDOOR"}, categories

    def test_default_weather_covers_every_day(self) -> None:
        """`None` 键作为默认天气，应覆盖所有查不到具体日期的天。"""
        pois = [make_poi(1, category="OUTDOOR"), make_poi(2, category="INDOOR")]
        clear = Packer().plan(
            start_date=DAY,
            days=2,
            candidates=[cand(p, crowd=0) for p in pois],
            tourist=tourist(),
            weather_by_day={None: "CLEAR"},
        )
        assert "OUTDOOR" in {a.category for d in clear.days for a in d.activities}

    def test_outdoor_still_allowed_on_clear_day(self) -> None:
        """对照组：晴天户外正常可排，证明上面的过滤不是「一律禁户外」。"""
        poi = make_poi(1, category="OUTDOOR")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(poi, crowd=0)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        assert result.days[0].activity_count == 1

    def test_reason_mentions_weather_avoidance(self) -> None:
        pois = [make_poi(1, category="INDOOR"), make_poi(2, category="INDOOR")]
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(p, crowd=0) for p in pois],
            tourist=tourist(),
            weather_by_day={DAY: "STORM"},
        )
        assert any("户外" in r and "天气" in r for r in result.reasons)


# ======================================================================
# 4. BR-09 高拥挤度错峰
# ======================================================================
class TestCrowdShift:
    def test_busy_poi_not_in_rush_window(self) -> None:
        """验收标准：拥挤度 ≥80 的 POI 时段均不在 10:00–15:00。"""
        busy = make_poi(1, open_time="09:00", close_time="20:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(busy, crowd=95)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        acts = result.days[0].activities
        # 要么排不进去，要么必须避开高峰窗口
        for act in acts:
            start = act.start.hour * 60 + act.start.minute
            end = act.end.hour * 60 + act.end.minute
            assert not (start < 15 * 60 and end > 10 * 60), f"{act.name} 落在 10:00–15:00 高峰内"

    def test_busy_poi_is_shifted_flag_set(self) -> None:
        busy = make_poi(1, open_time="09:00", close_time="20:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(busy, crowd=90)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        acts = result.days[0].activities
        if acts:
            assert acts[0].crowd_shifted is True
            assert acts[0].start >= time(15, 0)

    def test_busy_poi_closing_before_rush_ends_is_skipped(self) -> None:
        """15:00 前就关门的高拥挤 POI 没法错峰，只能放弃。"""
        busy = make_poi(1, open_time="09:00", close_time="14:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(busy, crowd=95)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        assert result.days[0].activity_count == 0

    def test_low_crowd_poi_not_shifted(self) -> None:
        poi = make_poi(1, open_time="09:00", close_time="18:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(poi, crowd=20)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        acts = result.days[0].activities
        assert acts and acts[0].crowd_shifted is False
        assert acts[0].start == time(9, 0)

    def test_unknown_crowd_is_not_shifted(self) -> None:
        """拥挤度数据缺失时不触发错峰（无法判断是否拥挤）。"""
        poi = make_poi(1, open_time="09:00", close_time="18:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(poi, crowd=None)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        assert result.days[0].activities[0].crowd_shifted is False


# ======================================================================
# 5. BR-07 通勤超 60 分钟标注
# ======================================================================
class TestLongTransfer:
    def test_long_transfer_flagged(self) -> None:
        """验收标准：通勤 > 60 分钟的相邻活动对带 longTransfer 标记。"""
        a = make_poi(1, open_time="09:00", close_time="18:00")
        b = make_poi(2, open_time="09:00", close_time="18:00")
        matrix = {(1, 2): 90, (2, 1): 90}
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(x, crowd=0) for x in (a, b)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
            travel_minutes=matrix,
        )
        acts = result.days[0].activities
        assert len(acts) == 2
        second = acts[1]
        assert second.travel_minutes == 90
        assert second.long_transfer is True

    def test_short_transfer_not_flagged(self) -> None:
        a = make_poi(1, open_time="09:00", close_time="18:00")
        b = make_poi(2, open_time="09:00", close_time="18:00")
        matrix = {(1, 2): 25, (2, 1): 25}
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(x, crowd=0) for x in (a, b)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
            travel_minutes=matrix,
        )
        acts = result.days[0].activities
        assert len(acts) == 2
        assert acts[1].long_transfer is False

    def test_boundary_60_minutes_not_flagged(self) -> None:
        """恰好 60 分钟不算「> 60」，不应标注。"""
        a = make_poi(1, open_time="09:00", close_time="18:00")
        b = make_poi(2, open_time="09:00", close_time="18:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(x, crowd=0) for x in (a, b)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
            travel_minutes={(1, 2): 60, (2, 1): 60},
        )
        acts = result.days[0].activities
        assert len(acts) == 2
        assert acts[1].long_transfer is False


# ======================================================================
# 6. BR-06 单日 ≤ 10 小时
# ======================================================================
class TestDailyLimit:
    def test_daily_total_within_ten_hours(self) -> None:
        """验收标准：单日活动总时长（含通勤）≤ 10 小时。"""
        pois = [make_poi(i, open_time="08:00", close_time="22:00") for i in range(1, 16)]
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(p, crowd=0) for p in pois],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        assert result.days[0].total_minutes <= 10 * 60

    def test_many_pois_do_not_exceed_one_day(self) -> None:
        """30 个候选塞进 1 天，也不能超 10 小时。"""
        pois = [make_poi(i, open_time="00:00", close_time="23:59") for i in range(1, 31)]
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(p, crowd=0) for p in pois],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        day = result.days[0]
        assert day.total_minutes <= 10 * 60
        for act in day.activities:
            assert act.end <= time(19, 0), "活动结束时间超过了 09:00+10h"

    def test_visit_duration_matches_constant(self) -> None:
        poi = make_poi(1, open_time="09:00", close_time="18:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(poi, crowd=0)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        assert result.days[0].activities[0].duration_minutes == DEFAULT_VISIT_MINUTES


# ======================================================================
# 7. 活动不足 → 自由时段
# ======================================================================
class TestFreeSlot:
    def test_insufficient_activities_marks_free_slot(self) -> None:
        """验收标准：某天可安排活动 < 2 个时插入自由活动时段并提示周边 POI。"""
        poi = make_poi(1)
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(poi, crowd=0)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        day = result.days[0]
        assert day.activity_count == 1
        assert day.free_slot is True
        assert day.free_slot_hint, "自由时段应给出周边可选 POI 提示"

    def test_zero_activity_marks_free_slot(self) -> None:
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        assert result.days[0].free_slot is True

    def test_enough_activities_no_free_slot(self) -> None:
        pois = [make_poi(i) for i in range(1, 6)]
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(p, crowd=0) for p in pois],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        assert result.days[0].activity_count >= 2
        assert result.days[0].free_slot is False

    def test_reason_mentions_free_slot(self) -> None:
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(make_poi(1), crowd=0)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
        )
        assert any("自由活动" in r for r in result.reasons)


# ======================================================================
# 8. 多方案差异化
# ======================================================================
def _many_candidates(n: int = 24) -> list[Candidate]:
    pois = []
    for i in range(1, n + 1):
        category = "OUTDOOR" if i % 3 == 0 else "INDOOR"
        price = float((i * 37) % 200)
        tags = ("人文历史",) if i % 2 else ("自然风光",)
        pois.append(make_poi(i, category=category, price=price, tags=tags))
    return [cand(p, crowd=(p.id * 7) % 100) for p in pois]


class TestMultiPlan:
    def test_returns_between_one_and_three_plans(self) -> None:
        engine = StrategyEngine()
        plans = engine.plan(
            _many_candidates(),
            PlanRequest(
                start_date=DAY,
                days=4,
                tourist=tourist(("人文历史",), budget=8000.0),
                weather_by_day={DAY: "CLEAR"},
            ),
        )
        assert 1 <= len(plans) <= 3

    def test_plans_have_acceptable_overlap(self) -> None:
        """验收标准：方案间 POI 重合度 < 70%。"""
        engine = StrategyEngine()
        plans = engine.plan(
            _many_candidates(),
            PlanRequest(
                start_date=DAY,
                days=4,
                tourist=tourist(("人文历史",), budget=8000.0),
                weather_by_day={DAY: "CLEAR"},
            ),
        )
        for i in range(len(plans)):
            for j in range(i + 1, len(plans)):
                ratio = overlap_ratio(plans[i].poi_ids, plans[j].poi_ids)
                assert ratio < MAX_OVERLAP_RATIO, f"方案 {i}/{j} 重合度 {ratio:.2f}"

    def test_each_plan_has_at_least_three_reasons(self) -> None:
        plans = StrategyEngine().plan(
            _many_candidates(),
            PlanRequest(
                start_date=DAY,
                days=2,
                tourist=tourist(),
                weather_by_day={DAY: "CLEAR"},
            ),
        )
        for plan in plans:
            # 第 1 条是方案标签，正文理由仍需 >= 3
            assert len(plan.reasons) >= 4

    def test_reasons_have_data_source_annotation(self) -> None:
        plans = StrategyEngine(max_plans=1).plan(
            _many_candidates(),
            PlanRequest(
                start_date=DAY,
                days=2,
                tourist=tourist(),
                weather_by_day={DAY: "CLEAR"},
            ),
        )
        text = "\n".join(plans[0].reasons)
        assert "依据：" in text

    def test_overlap_ratio_uses_smaller_set(self) -> None:
        """用较小集合做分母，比 Jaccard 严格。"""
        a = frozenset({1, 2, 3})
        b = frozenset({1, 2, 3, 4, 5, 6, 7})
        assert overlap_ratio(a, b) == 1.0
        assert overlap_ratio(frozenset(), b) == 0.0

    def test_max_plans_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError):
            StrategyEngine(max_plans=5)

    def test_empty_candidates_raises(self) -> None:
        with pytest.raises(ValueError, match="候选 POI 为空"):
            StrategyEngine().plan(
                [],
                PlanRequest(
                    start_date=DAY,
                    days=1,
                    tourist=tourist(),
                    weather_by_day={DAY: "CLEAR"},
                ),
            )

    def test_must_visit_prefers_those_pois(self) -> None:
        """必去项应尽量进入方案。"""
        candidates = _many_candidates(20)
        target = 20  # 排在候选池最后一个，正常情况下不容易被选中
        plans = StrategyEngine(max_plans=1).plan(
            candidates,
            PlanRequest(
                start_date=DAY,
                days=4,
                tourist=tourist(),
                weather_by_day={DAY: "CLEAR"},
            ),
            must_visit=[target],
        )
        assert target in plans[0].poi_ids


# ======================================================================
# 9. 通勤矩阵
# ======================================================================
class TestTravelMatrix:
    def test_diagonal_is_zero(self) -> None:
        m = TravelMatrix({(1, 1): 999, (1, 2): 30})
        assert m.get(1, 1) == 0

    def test_unknown_returns_none(self) -> None:
        m = TravelMatrix({(1, 2): 30})
        assert m.get(2, 1) is None, "缺失应为 None，不能返回 0"

    def test_negative_clamped_to_zero(self) -> None:
        m = TravelMatrix({(1, 2): -50})
        assert m.get(1, 2) == 0

    def test_build_matrix_fills_diagonal(self) -> None:
        pois = [make_poi(1), make_poi(2)]
        m = build_matrix(pois, {(1, 2): 25})
        assert m.get(1, 1) == 0
        assert m.get(2, 2) == 0
        assert m.get(1, 2) == 25

    def test_missing_pair_falls_back_conservatively(self) -> None:
        """矩阵缺项时 Packer 用保守估计，而不是当 0 分钟。"""
        a = make_poi(1, open_time="09:00", close_time="18:00")
        b = make_poi(2, open_time="09:00", close_time="18:00")
        result = Packer().plan(
            start_date=DAY,
            days=1,
            candidates=[cand(x, crowd=0) for x in (a, b)],
            tourist=tourist(),
            weather_by_day={DAY: "CLEAR"},
            travel_minutes={},
        )
        acts = result.days[0].activities
        assert len(acts) == 2
        assert acts[1].travel_minutes > 0


# ======================================================================
# 10. 推荐理由
# ======================================================================
class TestReasons:
    def test_at_least_three_reasons_always(self) -> None:
        plans = [DayPlan(day=DAY)]
        reasons = build_reasons(plans, {DAY: "CLEAR"}, Weights())
        assert len(reasons) >= 3

    def test_reason_mentions_weights(self) -> None:
        reasons = build_reasons([DayPlan(day=DAY)], {DAY: "CLEAR"}, Weights())
        assert any("权重" in r for r in reasons)

    def test_reason_mentions_long_transfer(self) -> None:
        act = Activity(
            poi_id=1,
            name="兵马俑",
            category="INDOOR",
            start=time(13, 0),
            end=time(14, 30),
            price=120.0,
            crowd_index=10,
            travel_minutes=95,
            long_transfer=True,
        )
        plan = DayPlan(day=DAY, activities=[act])
        reasons = build_reasons([plan], {DAY: "CLEAR"}, Weights())
        assert any("长距离通勤" in r for r in reasons)


# ======================================================================
# 11. 纯净层约束（architecture.md 分层约束第 3 条）
# ======================================================================
class TestPureLayer:
    """`app/engine/` 不许 import models / adapters / sqlalchemy。

    这条约束是「算法能脱离数据库与网络单测」的前提。用静态扫描守住它，
    比靠 code review 记住要可靠——以后谁在 engine 里加一行 `from app.models import`，
    这里会立刻红。
    """

    FORBIDDEN = ("app.models", "app.adapters", "sqlalchemy", "alembic")

    def test_engine_modules_import_only_stdlib_and_engine(self) -> None:
        import re
        from pathlib import Path

        engine_dir = Path(__file__).resolve().parent.parent / "app" / "engine"
        offenders: list[str] = []
        for path in sorted(engine_dir.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            for line in source.splitlines():
                stripped = line.strip()
                if not (stripped.startswith("import ") or stripped.startswith("from ")):
                    continue
                if stripped.startswith("from __future__"):
                    continue
                # 抓 `from X import` / `import X` 里的模块名
                match = re.match(r"(?:from|import)\s+([\w.]+)", stripped)
                if not match:
                    continue
                module = match.group(1)
                if any(module == bad or module.startswith(bad + ".") for bad in self.FORBIDDEN):
                    offenders.append(f"{path.name}: {stripped}")
        assert not offenders, "engine 层出现越界依赖:\n" + "\n".join(offenders)

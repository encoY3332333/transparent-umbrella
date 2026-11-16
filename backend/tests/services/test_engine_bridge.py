"""`#6` 排程引擎 → `#4` 编排协议的桥接测试（Issue #4）。

**为什么用假引擎而不是真的 `StrategyEngine`**：`#6`（PR #32）还没合并，
直接 import 会让这个测试在 main 上是红的。桥接层要测的是**映射是否正确**，
不是排程算法算得对不对——后者归 `tests/test_strategy_engine.py`。

真接口形状照抄自 PR #32 分支：
    PlanRequest(start_date, days, tourist, weather_by_day, travel_minutes)
    StrategyEngine.plan(candidates, request, *, must_visit=()) -> list[PlanResult]
    PlanResult(days: tuple[DayPlan, ...], reasons, weights, poi_ids)
    DayPlan(day, activities, free_slot, free_slot_hint, total_minutes)
    Activity(poi_id, name, category, start: time, end: time, price, crowd_index, ...)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

import pytest

from app.engine.protocols import Candidate, PlanContext, Requirement
from app.engine.selector import Poi
from app.services.engine_bridge import StrategyEnginePacker, _to_minute


def poi(poi_id: int, name: str = "陕西历史博物馆") -> Poi:
    return Poi(
        id=poi_id,
        name=name,
        city="西安",
        category="SIGHT",
        lat=34.22,
        lng=108.94,
        open_time="09:00",
        close_time="17:00",
        price=120.0,
        capacity=5000,
        tags=("人文历史",),
        status="PUBLISHED",
    )


def requirement(**kwargs: object) -> Requirement:
    base: dict[str, object] = {
        "city": "西安",
        "start_date": date(2026, 12, 1),
        "days": 2,
        "budget": 6000.0,
        "party_size": 2,
        "preference_tags": ("人文历史",),
        "must_visit": (205,),
    }
    base.update(kwargs)
    return Requirement(**base)  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# 与 #6 同形的假数据类
# ----------------------------------------------------------------------
@dataclass
class FakeActivity:
    poi_id: int
    name: str = "陕西历史博物馆"
    category: str = "SIGHT"
    start: time = time(9, 0)
    end: time = time(11, 0)
    price: float = 120.0
    crowd_index: int | None = 42
    travel_minutes: int = 30
    long_transfer: bool = False
    crowd_shifted: bool = True


@dataclass
class FakeDay:
    day: date
    activities: list[FakeActivity] = field(default_factory=list)
    total_minutes: int = 300
    free_slot: bool = False


@dataclass
class FakePlanResult:
    days: tuple[FakeDay, ...]
    reasons: tuple[str, ...] = ()

    @property
    def total_cost(self) -> float:
        return sum(a.price for d in self.days for a in d.activities)


class FakeEngine:
    def __init__(self, results: list[FakePlanResult]) -> None:
        self._results = results
        self.seen_request: object | None = None
        self.seen_must: tuple[int, ...] = ()

    def plan(self, candidates, request, *, must_visit=()):
        self.seen_request = request
        self.seen_must = tuple(must_visit)
        return self._results


class TestMapping:
    def test_requirement_becomes_plan_request(self) -> None:
        """`Requirement` 的字段要正确落进 `PlanRequest`，尤其是总预算与开始日期。"""
        engine = FakeEngine([FakePlanResult(days=(FakeDay(day=date(2026, 12, 1)),))])
        packer = StrategyEnginePacker(engine)

        packer.plan(
            requirement(),
            [Candidate(poi=poi(205))],
            PlanContext(requirement=requirement(), weather_by_day={None: "晴"}),
        )

        req = engine.seen_request
        assert req.start_date == date(2026, 12, 1)
        assert req.days == 2
        # 传总预算而不是人均：`#6` 用总额归一化门票价格
        assert req.tourist.budget == 6000.0
        assert req.tourist.preference_tags == frozenset({"人文历史"})
        assert req.weather_by_day == {None: "晴"}
        # must_visit 要透传，否则「必去」在排程阶段就丢了
        assert engine.seen_must == (205,)

    def test_empty_travel_matrix_becomes_none(self) -> None:
        """空矩阵传 None：避免 `#6` 误判成「有路网数据只是全 0」。"""
        engine = FakeEngine([FakePlanResult(days=(FakeDay(day=date(2026, 12, 1)),))])
        StrategyEnginePacker(engine).plan(
            requirement(),
            [Candidate(poi=poi(205))],
            PlanContext(requirement=requirement()),
        )
        assert engine.seen_request.travel_minutes is None

    def test_activity_maps_to_draft_with_poi_object(self) -> None:
        """`#6` 的 Activity 只有 poi_id，必须反查成 Poi 对象。"""
        engine = FakeEngine(
            [
                FakePlanResult(
                    days=(FakeDay(day=date(2026, 12, 1), activities=[FakeActivity(poi_id=205)]),)
                )
            ]
        )
        drafts = StrategyEnginePacker(engine).plan(
            requirement(),
            [Candidate(poi=poi(205, "兵马俑"))],
            PlanContext(requirement=requirement()),
        )

        act = drafts[0].activities[0]
        assert act.poi.id == 205
        # 名字取自候选池里的 Poi，不是假数据里的 name 字段
        assert act.poi.name == "兵马俑"
        # time → 当日分钟数
        assert (act.start_minute, act.end_minute) == (540, 660)
        assert act.crowd_shifted is True
        assert act.travel_minutes == 30

    def test_day_index_uses_enumeration(self) -> None:
        """day_index 必须按顺序枚举，不能从日期反算——中间空天会越界。"""
        engine = FakeEngine(
            [
                FakePlanResult(
                    days=(
                        FakeDay(day=date(2026, 12, 1), activities=[FakeActivity(poi_id=1)]),
                        FakeDay(day=date(2026, 12, 2), activities=[]),
                        FakeDay(day=date(2026, 12, 3), activities=[FakeActivity(poi_id=2)]),
                    )
                )
            ]
        )
        drafts = StrategyEnginePacker(engine).plan(
            requirement(days=3),
            [Candidate(poi=poi(1)), Candidate(poi=poi(2))],
            PlanContext(requirement=requirement(days=3)),
        )
        assert [a.day_index for a in drafts[0].activities] == [0, 2]

    def test_unknown_poi_is_dropped_with_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """候选池里查不到的 POI 要丢弃并记日志，不能塞假 POI 进库。"""
        engine = FakeEngine(
            [
                FakePlanResult(
                    days=(
                        FakeDay(
                            day=date(2026, 12, 1),
                            activities=[FakeActivity(poi_id=999, name="已下架景点")],
                        ),
                    )
                )
            ]
        )
        with caplog.at_level("WARNING"):
            drafts = StrategyEnginePacker(engine).plan(
                requirement(), [Candidate(poi=poi(205))], PlanContext(requirement=requirement())
            )
        # 唯一一套方案的活动全被丢弃 → 整套方案不返回，避免空行程
        assert drafts == []
        assert "不在候选池" in caplog.text
        assert "999" in caplog.text

    def test_title_uses_variant_label(self) -> None:
        """`#6` 把方案标签放在 reasons[0] 的【】里，标题要能取到。"""
        engine = FakeEngine(
            [
                FakePlanResult(
                    days=(FakeDay(day=date(2026, 12, 1), activities=[FakeActivity(poi_id=1)]),),
                    reasons=("【省钱方案】", "把门票压到最低", "BR-23 权重：cost 上调"),
                )
            ]
        )
        drafts = StrategyEnginePacker(engine).plan(
            requirement(), [Candidate(poi=poi(1))], PlanContext(requirement=requirement())
        )
        assert drafts[0].title == "西安 2 日 · 省钱优先线"

    def test_reasons_kept_without_fake_basis(self) -> None:
        """理由原样保留，但不臆造 `basis`——评审时无法核查的规则编号比留空更糟。"""
        engine = FakeEngine(
            [
                FakePlanResult(
                    days=(FakeDay(day=date(2026, 12, 1), activities=[FakeActivity(poi_id=1)]),),
                    reasons=("【均衡方案】", "偏好与通勤比较平衡"),
                )
            ]
        )
        drafts = StrategyEnginePacker(engine).plan(
            requirement(), [Candidate(poi=poi(1))], PlanContext(requirement=requirement())
        )
        assert drafts[0].reasons[0].text == "【均衡方案】"
        assert drafts[0].reasons[1].text == "偏好与通勤比较平衡"
        assert drafts[0].reasons[0].basis == ""

    def test_totals_are_aggregated(self) -> None:
        engine = FakeEngine(
            [
                FakePlanResult(
                    days=(
                        FakeDay(
                            day=date(2026, 12, 1),
                            activities=[FakeActivity(poi_id=1, price=50.0)],
                            total_minutes=300,
                        ),
                        FakeDay(
                            day=date(2026, 12, 2),
                            activities=[FakeActivity(poi_id=2, price=70.0)],
                            total_minutes=240,
                        ),
                    )
                )
            ]
        )
        drafts = StrategyEnginePacker(engine).plan(
            requirement(),
            [Candidate(poi=poi(1)), Candidate(poi=poi(2))],
            PlanContext(requirement=requirement()),
        )
        assert drafts[0].total_cost == 120.0
        assert drafts[0].total_minutes == 540


class TestHelpers:
    def test_to_minute_accepts_time_and_int(self) -> None:
        assert _to_minute(time(9, 30)) == 570
        assert _to_minute(time(0, 5)) == 5
        assert _to_minute(1234) == 1234


class TestBuild:
    def test_build_packer_returns_none_when_engine_missing(self, monkeypatch) -> None:
        """`#6` 未合入时必须返回 None（由 deps 回落占位），而不是抛 ImportError。"""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "app.engine.strategy_engine":
                raise ImportError("simulated: PR #32 not merged")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        from app.services.engine_bridge import build_packer

        assert build_packer() is None

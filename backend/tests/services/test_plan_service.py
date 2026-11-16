"""行程生成编排的单元测试（Issue #4）。

三条重点，对应 Issue 的验收标准：

1. `calls == ["select", "plan", "validate"]` —— 顺序不能换；
2. 落库中途失败时**一条 `Itinerary` 都不留**（事务边界在 service）；
3. 外部调用超限（BR-10）时抛出的是 `EXTERNAL_CALL_LIMIT_EXCEEDED`，
   而不是被 `BaseAdapter` 的重试逻辑吞成「降级」。

用假实现而不是真 engine：`#6` / `#7` 还没合入，而本 Issue 要测的是**编排**，
不是排程算法本身。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import BusinessError, ErrorCode
from app.engine.protocols import (
    ActivityDraft,
    Candidate,
    Conflict,
    PlanContext,
    PlanDraft,
    Reason,
    Requirement,
)
from app.engine.selector import Poi
from app.models.base import Base
from app.models.itinerary import Activity, Itinerary, ItineraryDay
from app.services.plan_service import LONG_TRANSFER_MINUTES, MAX_PLANS, PlanService


# ----------------------------------------------------------------------
# 夹具
# ----------------------------------------------------------------------
@pytest.fixture
def session() -> Iterator[Session]:
    """独立的内存库。不复用 conftest 的 `client`——这里测的是 service，不需要 HTTP。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as s:
        yield s
    engine.dispose()


def make_poi(poi_id: int = 1, *, name: str = "陕西历史博物馆", price: float = 0.0) -> Poi:
    return Poi(
        id=poi_id,
        name=name,
        city="西安",
        category="SIGHT",
        lat=34.22,
        lng=108.94,
        open_time="09:00",
        close_time="17:00",
        price=price,
        capacity=5000,
        tags=("人文历史",),
        status="PUBLISHED",
    )


def requirement(**kwargs: object) -> Requirement:
    defaults: dict[str, object] = {
        "city": "西安",
        "start_date": date(2026, 12, 1),
        "days": 2,
        "budget": 6000.0,
        "party_size": 2,
    }
    defaults.update(kwargs)
    return Requirement(**defaults)  # type: ignore[arg-type]


def make_draft(title: str = "西安 2 日", *, day_index: int = 0, poi_id: int = 1) -> PlanDraft:
    return PlanDraft(
        title=title,
        activities=(
            ActivityDraft(
                poi=make_poi(poi_id),
                day_index=day_index,
                start_minute=9 * 60,
                end_minute=11 * 60,
                travel_minutes=30,
                crowd_index=40,
            ),
        ),
        reasons=(Reason(text="偏好匹配：人文历史", basis="BR-23"),),
        total_cost=120.0,
        total_minutes=120,
    )


class FakeSelector:
    def __init__(self, calls: list[str], *, count: int = 3) -> None:
        self.calls = calls
        self.count = count

    def select(self, req: Requirement, pois: list[Poi]) -> list[Candidate]:
        self.calls.append("select")
        return [Candidate(poi=make_poi(i + 1)) for i in range(self.count)]


class FakePacker:
    def __init__(self, calls: list[str], *, drafts: int = 2) -> None:
        self.calls = calls
        self.drafts = drafts

    def plan(
        self, req: Requirement, candidates: list[Candidate], context: PlanContext
    ) -> list[PlanDraft]:
        self.calls.append("plan")
        return [make_draft(f"方案 {i + 1}") for i in range(self.drafts)]


class FakeChecker:
    def __init__(self, calls: list[str], *, conflicts: list[Conflict] | None = None) -> None:
        self.calls = calls
        self.conflicts = conflicts or []

    def validate(self, plan: PlanDraft) -> list[Conflict]:
        self.calls.append("validate")
        return self.conflicts


def build(calls: list[str], **kwargs: object) -> PlanService:
    return PlanService(
        selector=FakeSelector(calls, count=kwargs.get("count", 3)),  # type: ignore[arg-type]
        packer=FakePacker(calls, drafts=kwargs.get("drafts", 2)),  # type: ignore[arg-type]
        feasibility=FakeChecker(calls, conflicts=kwargs.get("conflicts")),  # type: ignore[arg-type]
    )


# ----------------------------------------------------------------------
# 顺序
# ----------------------------------------------------------------------
class TestOrder:
    def test_calls_select_plan_validate_in_order(self, session: Session) -> None:
        """验收标准原文：三个子模块按 select → plan → validate 顺序被调用。"""
        calls: list[str] = []
        service = build(calls)

        service.generate(session, requirement())

        # 两套方案 → select 一次、plan 一次、validate 两次
        assert calls == ["select", "plan", "validate", "validate"]

    def test_validate_runs_once_per_draft(self, session: Session) -> None:
        calls: list[str] = []
        service = build(calls)

        service.generate(session, requirement())

        assert calls.count("validate") == 2


# ----------------------------------------------------------------------
# 落库
# ----------------------------------------------------------------------
class TestPersist:
    def test_persists_days_and_activities(self, session: Session) -> None:
        result = build([]).generate(session, requirement())

        assert len(result.plans) == 2
        itinerary = session.execute(select(Itinerary)).scalars().first()
        assert itinerary is not None and itinerary.status == "PROPOSED"
        assert itinerary.days == 2

        days = session.execute(select(ItineraryDay)).scalars().all()
        # 两套方案 × 2 天
        assert len(days) == 4
        # 每天都建出来了，哪怕当天没有活动（否则前端「第 2 天」会消失）
        assert {d.day_index for d in days} == {0, 1}

        activities = session.execute(select(Activity)).scalars().all()
        assert len(activities) == 2
        assert all(a.poi_name == "陕西历史博物馆" for a in activities)

    def test_long_transfer_flag_uses_threshold(self, session: Session) -> None:
        draft = PlanDraft(
            title="长途",
            activities=(
                ActivityDraft(
                    poi=make_poi(),
                    day_index=0,
                    start_minute=600,
                    end_minute=660,
                    travel_minutes=LONG_TRANSFER_MINUTES + 1,
                ),
            ),
        )
        service = PlanService(
            selector=FakeSelector([]),  # type: ignore[arg-type]
            packer=_OneDraftPacker(draft),  # type: ignore[arg-type]
            feasibility=FakeChecker([]),  # type: ignore[arg-type]
        )
        service.generate(session, requirement(days=1))

        act = session.execute(select(Activity)).scalars().one()
        assert act.long_transfer is True

    def test_batch_id_is_shared_by_plans(self, session: Session) -> None:
        build([]).generate(session, requirement())

        batches = {it.batch_id for it in session.execute(select(Itinerary)).scalars()}
        assert len(batches) == 1, "同一次生成的多套方案必须共享 batch_id，前端靠它「换一套」"

    def test_invalid_day_index_rolls_back_everything(self, session: Session) -> None:
        """子模块给出越界 day_index → 整个事务回滚，一条记录都不留。"""
        bad = PlanDraft(
            title="越界",
            activities=(ActivityDraft(poi=make_poi(), day_index=5, start_minute=0, end_minute=60),),
        )
        service = PlanService(
            selector=FakeSelector([]),  # type: ignore[arg-type]
            packer=_OneDraftPacker(bad),  # type: ignore[arg-type]
            feasibility=FakeChecker([]),  # type: ignore[arg-type]
        )

        with pytest.raises(ValueError):
            service.generate(session, requirement(days=1))

        assert session.execute(select(Itinerary)).scalars().all() == []
        assert session.execute(select(ItineraryDay)).scalars().all() == []


class _OneDraftPacker:
    def __init__(self, draft: PlanDraft) -> None:
        self._draft = draft

    def plan(
        self, req: Requirement, candidates: list[Candidate], context: PlanContext
    ) -> list[PlanDraft]:
        return [self._draft]


# ----------------------------------------------------------------------
# 失败语义
# ----------------------------------------------------------------------
class TestFailures:
    def test_empty_candidates_raises_no_candidate(self, session: Session) -> None:
        calls: list[str] = []
        service = build(calls, count=0)

        with pytest.raises(BusinessError) as exc:
            service.generate(session, requirement())

        assert exc.value.code is ErrorCode.PLAN_NO_CANDIDATE
        # 候选为空就不该继续往下走
        assert calls == ["select"]

    def test_no_drafts_raises_infeasible(self, session: Session) -> None:
        calls: list[str] = []
        service = build(calls, drafts=0)

        with pytest.raises(BusinessError) as exc:
            service.generate(session, requirement())

        assert exc.value.code is ErrorCode.PLAN_INFEASIBLE
        assert calls == ["select", "plan"]

    def test_all_drafts_with_error_conflict_raises_infeasible(self, session: Session) -> None:
        conflict = Conflict(code="BR-08", message="雨天排了户外景点", severity="ERROR")
        service = build([], conflicts=[conflict])

        with pytest.raises(BusinessError) as exc:
            service.generate(session, requirement())

        assert exc.value.code is ErrorCode.PLAN_INFEASIBLE
        assert session.execute(select(Itinerary)).scalars().all() == []

    def test_warn_conflict_is_kept(self, session: Session) -> None:
        conflict = Conflict(code="BR-07", message="通勤 75 分钟", severity="WARN", day_index=0)
        result = build([], conflicts=[conflict]).generate(session, requirement())

        assert len(result.plans) == 2
        assert result.plans[0].conflicts == [conflict]

    def test_plans_truncated_to_max(self, session: Session) -> None:
        calls: list[str] = []
        service = build(calls, drafts=MAX_PLANS + 2)

        result = service.generate(session, requirement())

        assert len(result.plans) == MAX_PLANS
        assert calls.count("validate") == MAX_PLANS, "超出的草稿不该再浪费一次校验"


class TestSelectorErrorTranslation:
    """`#5` 的 selector 抛的是 engine 自有异常，编排层必须翻译成业务错误码。

    不翻译的话会一路冒到 handlers 变成 500「服务端异常」，
    而真实原因只是「这个城市没导入景点」——排查方向完全被带偏。
    """

    def test_insufficient_poi_becomes_no_candidate(self, session: Session) -> None:
        from app.engine.selector import InsufficientPoiData

        class EmptySelector:
            def select(self, req: Requirement, pois: list[Poi]) -> list[Candidate]:
                raise InsufficientPoiData("西安", 3, 20)

        service = PlanService(
            selector=EmptySelector(),  # type: ignore[arg-type]
            packer=FakePacker([]),  # type: ignore[arg-type]
            feasibility=FakeChecker([]),  # type: ignore[arg-type]
        )

        with pytest.raises(BusinessError) as exc:
            service.generate(session, requirement())

        assert exc.value.code is ErrorCode.PLAN_NO_CANDIDATE
        # 提示里要带上真实数量，否则用户只知道「不够」但不知道还差多少
        assert "3" in str(exc.value.message) and "20" in str(exc.value.message)

    def test_must_visit_conflict_becomes_400(self, session: Session) -> None:
        from app.engine.selector import PoiSelectionError

        class ConflictSelector:
            def select(self, req: Requirement, pois: list[Poi]) -> list[Candidate]:
                raise PoiSelectionError("必去与必避冲突: [205]")

        service = PlanService(
            selector=ConflictSelector(),  # type: ignore[arg-type]
            packer=FakePacker([]),  # type: ignore[arg-type]
            feasibility=FakeChecker([]),  # type: ignore[arg-type]
        )

        with pytest.raises(BusinessError) as exc:
            service.generate(session, requirement())

        assert exc.value.code is ErrorCode.CONDITION_MUST_VISIT_CONFLICT
        assert exc.value.resolved_status == 400, "用户输入问题不该回 5xx"


# ----------------------------------------------------------------------
# BR-10 外部调用预算
# ----------------------------------------------------------------------
class TestCallBudget:
    def test_budget_resets_between_plans(self) -> None:
        from app.adapters import call_budget

        with call_budget.budget(limit=2):
            assert call_budget.record() == 1
            assert call_budget.record() == 2
            call_budget.check()  # 恰好用完不抛

        # 出了 with 块计数回到之前的值（默认 0）
        assert call_budget.record() == 1

    def test_exceed_raises_business_error(self) -> None:
        from app.adapters import call_budget

        with call_budget.budget(limit=1):
            assert call_budget.limit() == 1
            call_budget.record()
            call_budget.check()  # 第 1 次，正好用完额度
            call_budget.record()  # 第 2 次，超了
            with pytest.raises(BusinessError) as exc:
                call_budget.check()

        assert exc.value.code is ErrorCode.EXTERNAL_CALL_LIMIT_EXCEEDED
        # 退出 with 后上限要还原，否则后面所有请求都被卡在 1 次
        assert call_budget.limit() == call_budget.EXTERNAL_CALL_LIMIT

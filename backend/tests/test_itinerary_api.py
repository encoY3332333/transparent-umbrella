"""`POST /api/itineraries/generate` 与页面的接口测试（Issue #4）。

这里**不测算法**（那是 `tests/services/test_plan_service.py` 的事），
只测 HTTP 契约：camelCase 出参、错误码、以及 HTMX 片段必须返回 200。

用假的 service 覆盖依赖，避免测试依赖 `#5` / `#6` / `#7` 是否已合入——
本 Issue 的接口形状不该因为别人还没写完而飘。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_plan_service
from app.core.config import Settings
from app.core.deps import get_db
from app.core.errors import BusinessError, ErrorCode
from app.engine.protocols import Requirement
from app.engine.selector import Poi
from app.main import create_app
from app.models.base import Base
from app.models.itinerary import Activity, Itinerary, ItineraryDay
from app.services.plan_service import GeneratedPlan, GenerationResult


def _poi(poi_id: int = 205, name: str = "陕西历史博物馆", price: float = 0.0) -> Poi:
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


@pytest.fixture
def db() -> Iterator[Session]:
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


def _seed(session: Session, *, title: str = "西安 2 日 · 人文线", days: int = 2) -> Itinerary:
    """直接造一条落库的行程，模拟 `PlanService` 的产出（事务由测试控制）。"""
    itinerary = Itinerary(
        batch_id="batch-1",
        title=title,
        status="PROPOSED",
        city="西安",
        start_date=date(2026, 12, 1),
        days=days,
        party_size=2,
        budget=6000.0,
        total_cost=120.0,
        total_minutes=120,
        reasons_json='[{"text": "偏好匹配：人文历史", "basis": "BR-23"}]',
        degraded_json="[]",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    for index in range(days):
        itinerary.day_plans.append(
            ItineraryDay(day_index=index, day_date=date(2026, 12, 1 + index))
        )
    itinerary.day_plans[0].activities.append(
        Activity(
            poi_id=205,
            poi_name="陕西历史博物馆",
            category="SIGHT",
            start_minute=540,
            end_minute=690,
            price=120.0,
            travel_minutes=75,
            crowd_index=42,
            crowd_shifted=True,
            long_transfer=True,
            locked=False,
        )
    )
    return itinerary


class FakeService:
    """记录被调用时的入参，并写入一条行程；用于验证「路由把请求翻译对了」。"""

    def __init__(self, session: Session, *, error: BusinessError | None = None) -> None:
        self.session = session
        self.error = error
        self.seen: list[Requirement] = []

    def generate(self, session: Session, requirement: Requirement, *_, **__) -> GenerationResult:
        self.seen.append(requirement)
        if self.error is not None:
            raise self.error
        itinerary = _seed(session, days=requirement.days)
        session.add(itinerary)
        session.commit()
        return GenerationResult(
            batch_id="batch-1",
            plans=[GeneratedPlan(itinerary=itinerary, conflicts=[])],
            duration_ms=42,
            degraded=["WEATHER"],
        )


@pytest.fixture
def app_client(db: Session) -> Iterator[tuple[TestClient, FakeService]]:
    settings = Settings(app_env="test", log_level="WARNING")
    app = create_app(settings)
    service = FakeService(db)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_plan_service] = lambda: service

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, service
    app.dependency_overrides.clear()


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "destCity": "西安",
        "startDate": "2026-12-01",
        "endDate": "2026-12-04",
        "budget": 6000,
        "partySize": 2,
        "preferenceTags": ["人文历史"],
        "mustVisit": [205],
        "avoidPOI": [310],
        "variantCount": 2,
    }
    body.update(overrides)
    return body


class TestGenerateJson:
    def test_returns_camel_case_payload(self, app_client: tuple[TestClient, FakeService]) -> None:
        client, _ = app_client
        response = client.post("/api/itineraries/generate", json=_payload())

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "OK"
        data = body["data"]
        assert data["durationMs"] == 42
        assert data["degraded"] == ["WEATHER"]

        plan = data["itineraries"][0]
        # 出参必须是 camelCase——前端照着 api.md 写的
        assert plan["dayCount"] == 4
        assert plan["budgetBreakdown"] == {"ticket": 120.0}
        assert plan["reasons"][0]["basis"] == "BR-23"

        activity = plan["days"][0]["activities"][0]
        assert activity["startTime"] == "09:00"
        assert activity["endTime"] == "11:30"
        assert activity["longTransfer"] is True
        assert activity["crowdShifted"] is True

    def test_days_include_free_days(self, app_client: tuple[TestClient, FakeService]) -> None:
        """没排活动的日子也要出现，否则前端「第 3 天」直接消失。"""
        client, _ = app_client
        plan = client.post("/api/itineraries/generate", json=_payload()).json()["data"][
            "itineraries"
        ][0]

        assert len(plan["days"]) == 4
        assert plan["days"][1]["freeSlot"] is True
        assert plan["days"][1]["activities"] == []

    def test_request_translated_to_requirement(
        self, app_client: tuple[TestClient, FakeService]
    ) -> None:
        client, service = app_client
        client.post("/api/itineraries/generate", json=_payload())

        req = service.seen[0]
        assert req.city == "西安"
        # 12-01 到 12-04 含首尾 = 4 天
        assert req.days == 4
        assert req.budget == 6000
        assert req.must_visit == (205,)
        assert req.avoid_poi == (310,)
        assert req.preference_tags == ("人文历史",)

    def test_reversed_dates_rejected_with_field(
        self, app_client: tuple[TestClient, FakeService]
    ) -> None:
        client, _ = app_client
        response = client.post(
            "/api/itineraries/generate",
            json=_payload(startDate="2026-12-04", endDate="2026-12-01"),
        )

        assert response.status_code == 400
        body = response.json()
        assert body["code"] == "CONDITION_INVALID_DATE_RANGE"
        # 前端要能定位到具体字段
        assert body["details"][0]["field"] == "endDate"

    def test_must_visit_overlap_rejected(self, app_client: tuple[TestClient, FakeService]) -> None:
        client, _ = app_client
        response = client.post(
            "/api/itineraries/generate", json=_payload(mustVisit=[205], avoidPOI=[205])
        )

        assert response.status_code == 400
        assert response.json()["code"] == "CONDITION_MUST_VISIT_CONFLICT"

    def test_business_error_maps_to_status(
        self, app_client: tuple[TestClient, FakeService]
    ) -> None:
        client, service = app_client
        service.error = BusinessError(code=ErrorCode.PLAN_NO_CANDIDATE)

        response = client.post("/api/itineraries/generate", json=_payload())

        assert response.status_code == 422
        assert response.json()["code"] == "PLAN_NO_CANDIDATE"

    def test_unknown_field_rejected(self, app_client: tuple[TestClient, FakeService]) -> None:
        """`extra="forbid"`：拼错字段名要报错，而不是被静默忽略。"""
        client, _ = app_client
        response = client.post("/api/itineraries/generate", json=_payload(destCitty="西安"))

        assert response.status_code == 400
        assert response.json()["code"] == "PARAM_INVALID"


class TestGenerateFragment:
    """HTMX 片段：无论成功失败都必须是 200 + HTML，否则 HTMX 不会替换目标节点。"""

    def test_form_post_renders_result(self, app_client: tuple[TestClient, FakeService]) -> None:
        client, _ = app_client
        response = client.post(
            "/api/itineraries/generate.fragment",
            data={
                "destCity": "西安",
                "startDate": "2026-12-01",
                "endDate": "2026-12-04",
                "budget": "6000",
                "partySize": "2",
                "preferenceTags": ["人文历史", "美食"],
            },
        )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "陕西历史博物馆" in response.text
        assert "已避峰" in response.text
        assert "部分数据不可用" in response.text  # degraded 提示

    def test_business_error_returns_html_200(
        self, app_client: tuple[TestClient, FakeService]
    ) -> None:
        client, service = app_client
        service.error = BusinessError(
            code=ErrorCode.PLAN_NO_CANDIDATE, message="西安 可用景点不足（0 个，至少需要 20 个）"
        )

        response = client.post(
            "/api/itineraries/generate.fragment",
            data={
                "destCity": "西安",
                "startDate": "2026-12-01",
                "endDate": "2026-12-04",
                "budget": "6000",
            },
        )

        assert response.status_code == 200, "HTMX 不换非 2xx 响应体，这里必须是 200"
        assert "PLAN_NO_CANDIDATE" in response.text
        assert "可用景点不足" in response.text

    def test_invalid_form_renders_error_fragment(
        self, app_client: tuple[TestClient, FakeService]
    ) -> None:
        client, _ = app_client
        response = client.post(
            "/api/itineraries/generate.fragment",
            data={
                "destCity": "西安",
                "startDate": "2026-12-01",
                "endDate": "2026-12-04",
                "budget": "abc",
            },
        )

        assert response.status_code == 200
        assert "PARAM_INVALID" in response.text
        assert "budget" in response.text


class TestPage:
    def test_new_page_renders_form(self, app_client: tuple[TestClient, FakeService]) -> None:
        client, _ = app_client
        response = client.get("/itineraries/new")

        assert response.status_code == 200
        assert 'hx-post="/api/itineraries/generate.fragment"' in response.text
        # 加载态文案不承诺百分比（真实耗时取决于外部接口重试）
        assert "3–10 秒" in response.text
        assert "%" not in response.text.split("plan-loading")[1][:400]

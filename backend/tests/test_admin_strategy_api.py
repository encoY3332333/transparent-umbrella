"""`/api/admin/strategies/**` 与配置页的接口测试（Issue #13 / UC-09）。

只测 HTTP 契约：camelCase 出参、`PARAM_INVALID` 的形态、二次确认的 200 分支、
以及配置页能正常渲染。校验规则本身在 `tests/services/test_strategy_service.py` 里测。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.deps import get_db
from app.main import create_app
from app.models.base import Base

BALANCED = {"preference": 0.10, "weather": 0.25, "crowd": 0.23, "travel": 0.14, "cost": 0.28}
# cost=0 且仍要满足和为 1：其余四项抬到合计 1.0
ZERO_COST = {"preference": 0.20, "weather": 0.30, "crowd": 0.30, "travel": 0.20, "cost": 0.0}


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


@pytest.fixture
def api(db: Session) -> Iterator[TestClient]:
    app = create_app(Settings(app_env="test", log_level="WARNING"))
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.clear()


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "weights": dict(BALANCED),
        "holidayFactors": {"春节": 2.2, "工作日": 1.0},
        "thresholds": {"dailyHours": 9, "maxWalkMinutes": 90},
    }
    body.update(overrides)
    return body


# ----------------------------------------------------------------------
# 读
# ----------------------------------------------------------------------
def test_current_defaults_to_version_zero(api: TestClient) -> None:
    body = api.get("/api/admin/strategies/current").json()
    assert body["code"] == "OK"
    assert body["data"]["version"] == 0
    # 出参必须是契约里的 camelCase
    assert body["data"]["weights"] == {
        "preference": 0.10,
        "weather": 0.25,
        "crowd": 0.23,
        "travel": 0.14,
        "cost": 0.28,
    }
    assert body["data"]["holidayFactors"]["春节"] == 2.2
    assert body["data"]["disabledFallbacks"] == []


def test_version_list_is_empty_before_first_publish(api: TestClient) -> None:
    body = api.get("/api/admin/strategies").json()
    assert body["data"] == []


# ----------------------------------------------------------------------
# 写
# ----------------------------------------------------------------------
def test_publish_returns_new_version(api: TestClient) -> None:
    body = api.post("/api/admin/strategies", json=_payload()).json()
    assert body["data"]["saved"] is True
    assert body["data"]["strategy"]["version"] == 1
    assert body["data"]["strategy"]["thresholds"]["dailyHours"] == 9
    # 发布后 current 立刻生效（AC-1）
    assert api.get("/api/admin/strategies/current").json()["data"]["version"] == 1


def test_publish_rejects_bad_sum_with_current_total(api: TestClient) -> None:
    bad = {"preference": 0.2, "weather": 0.2, "crowd": 0.2, "travel": 0.2, "cost": 0.3}
    response = api.post("/api/admin/strategies", json=_payload(weights=bad))
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "PARAM_INVALID"
    assert "1.1000" in body["message"]
    assert body["details"][0]["field"] == "weights"


def test_publish_rejects_out_of_range_weight(api: TestClient) -> None:
    # Pydantic 的 ge/le 在 schema 层就挡住，走 RequestValidationError → PARAM_INVALID
    response = api.post("/api/admin/strategies", json=_payload(weights={**BALANCED, "crowd": 1.5}))
    assert response.status_code == 400
    assert response.json()["code"] == "PARAM_INVALID"


def test_zero_weight_with_disabled_fallback_requires_confirm(api: TestClient) -> None:
    body = api.post(
        "/api/admin/strategies",
        json=_payload(weights=dict(ZERO_COST), disabledFallbacks=["cost"]),
    ).json()
    assert body["data"]["saved"] is False
    assert body["data"]["requiresConfirm"] is True
    assert body["data"]["warnings"]
    # 没确认就不该落库
    assert api.get("/api/admin/strategies").json()["data"] == []


def test_confirm_true_saves(api: TestClient) -> None:
    body = api.post(
        "/api/admin/strategies",
        json=_payload(weights=dict(ZERO_COST), disabledFallbacks=["cost"], confirm=True),
    ).json()
    assert body["data"]["saved"] is True
    assert body["data"]["strategy"]["disabledFallbacks"] == ["cost"]


def test_version_list_is_desc(api: TestClient) -> None:
    api.post("/api/admin/strategies", json=_payload())
    api.post("/api/admin/strategies", json=_payload(weights={**BALANCED, "cost": 0.281}))
    versions = [item["version"] for item in api.get("/api/admin/strategies").json()["data"]]
    assert versions == [2, 1]


# ----------------------------------------------------------------------
# 归一化与回滚
# ----------------------------------------------------------------------
def test_normalize_endpoint(api: TestClient) -> None:
    body = api.post(
        "/api/admin/strategies/normalize",
        # 归一化的输入必须每项都在 [0,1]：滑块本来就不会超出这个范围，
        # 「和为 1」才是它要解决的问题
        json={
            "weights": {"preference": 0.1, "weather": 0.2, "crowd": 0.3, "travel": 0.2, "cost": 0.4}
        },
    ).json()
    weights = body["data"]["weights"]
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-9)
    assert body["data"]["totalBefore"] == pytest.approx(1.2)


def test_rollback_creates_new_version(api: TestClient) -> None:
    api.post("/api/admin/strategies", json=_payload())
    api.post(
        "/api/admin/strategies",
        json=_payload(
            weights={"preference": 0.4, "weather": 0.2, "crowd": 0.2, "travel": 0.1, "cost": 0.1}
        ),
    )

    body = api.post("/api/admin/strategies/rollback/1").json()
    assert body["data"]["version"] == 3
    assert body["data"]["note"] == "回滚自 v1"
    assert body["data"]["weights"] == BALANCED
    # 回滚后 current 立刻是回滚出来的那一版（AC-3 的 5 秒内生效）
    assert api.get("/api/admin/strategies/current").json()["data"]["version"] == 3


def test_rollback_unknown_version_is_404(api: TestClient) -> None:
    response = api.post("/api/admin/strategies/rollback/99")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# ----------------------------------------------------------------------
# 页面
# ----------------------------------------------------------------------
def test_admin_page_renders_sliders(api: TestClient) -> None:
    response = api.get("/admin/strategy")
    assert response.status_code == 200
    html = response.text
    # 五项权重各有一个滑块 + 一个数字框
    for key in ("preference", "weather", "crowd", "travel", "cost"):
        assert f'id="w-{key}"' in html
    assert "一键归一化" in html
    assert "版本历史" in html


def test_admin_page_shows_published_version(api: TestClient) -> None:
    api.post("/api/admin/strategies", json=_payload())
    html = api.get("/admin/strategy").text
    assert "v1" in html
    assert "生效中" in html


# ----------------------------------------------------------------------
# 生成链路拿到的是「当前生效」的那一版权重（AC-1 的接线）
# ----------------------------------------------------------------------
def test_generation_context_uses_published_weights(api: TestClient, db: Session) -> None:
    """发布后的参数必须出现在下一次生成的上下文里。

    不跑完整生成（那要 POI 池 + 引擎），只验证 `_context()` 这一步：
    它是「谁来读策略表」的唯一入口，读错了后面的打分全错。
    """
    from datetime import date

    from app.api.itineraries import _context
    from app.engine.protocols import Requirement
    from app.schemas.itinerary import GenerateRequest

    api.post("/api/admin/strategies", json=_payload(weights=dict(ZERO_COST)))

    requirement = Requirement(
        city="西安", start_date=date(2026, 12, 1), days=2, budget=6000, party_size=2
    )
    payload = GenerateRequest.model_validate(
        {
            "destCity": "西安",
            "startDate": "2026-12-01",
            "endDate": "2026-12-03",
            "budget": 6000,
            "partySize": 2,
        }
    )
    context = _context(payload, requirement, db)
    assert context.strategy_weights is not None
    assert context.strategy_weights["cost"] == pytest.approx(0.0)
    assert context.strategy_weights["weather"] == pytest.approx(0.30)
    assert sum(context.strategy_weights.values()) == pytest.approx(1.0, abs=1e-9)

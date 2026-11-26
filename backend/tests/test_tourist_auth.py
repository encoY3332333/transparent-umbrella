"""UC-01 认证与偏好建档的测试（Issue #2）。

分两层：
- `TestAuthService` 直接调 service，把时间注入进去验证过期 / 频控 / 锁定，
  不依赖真实时钟等待；
- `TestAuthApi` 走 HTTP，验证 Cookie 下发、未登录语义、偏好超限的错误码。
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.deps import get_db
from app.core.errors import BusinessError, ErrorCode
from app.main import create_app
from app.models.base import Base
from app.models.tourist import Tourist
from app.services import auth_service


@pytest.fixture(autouse=True)
def _clean_code_store() -> None:
    """验证码存在进程内，用例之间必须清干净，否则频控会误伤下一条用例。"""
    auth_service.reset_state()
    yield
    auth_service.reset_state()


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        yield db


PHONE = "13800138000"


@pytest.fixture
def api_client(session: Session) -> Iterator[TestClient]:
    """HTTP 客户端：把 `get_db` 覆盖成用例自己的内存库。

    不直接用 conftest 的 `client`——那个客户端用的是应用自己建的引擎，
    和用例里 `Base.metadata.create_all()` 建出来的表不是同一个库（内存库
    每个连接一份），会报 `no such table: tourist`。
    """
    app = create_app(Settings(app_env="test", log_level="WARNING"))
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestAuthService:
    def test_request_code_returns_debug_code_in_test_env(self, session, settings, monkeypatch):
        monkeypatch.setenv("APP_ENV", "test")
        get_settings.cache_clear()
        expires_in, debug = auth_service.request_code(session, get_settings(), PHONE)
        assert expires_in == auth_service.CODE_TTL_SECONDS
        assert debug is not None and len(debug) == auth_service.CODE_LENGTH

    def test_request_code_hidden_in_production(self, session):
        # 直接构造而不是 model_copy：`is_production` 是 computed_field，
        # model_copy 不会重算它，复制出来的对象仍带着 dev 的 True/False 值。
        prod = Settings(app_env="prod")
        _, debug = auth_service.request_code(session, prod, PHONE)
        assert debug is None

    def test_second_request_within_cooldown_is_rejected(self, session, settings):
        auth_service.request_code(session, settings, PHONE)
        with pytest.raises(BusinessError) as exc:
            auth_service.request_code(session, settings, PHONE)
        assert exc.value.code is ErrorCode.SMS_SEND_TOO_FREQUENT

    def test_request_after_cooldown_succeeds(self, session, settings):
        base = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)
        auth_service.request_code(session, settings, PHONE, now=base)
        _, debug = auth_service.request_code(
            session, settings, PHONE, now=base + timedelta(seconds=61)
        )
        assert debug is not None

    def test_expired_code_is_rejected(self, session, settings):
        base = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)
        _, code = auth_service.request_code(session, settings, PHONE, now=base)
        with pytest.raises(BusinessError) as exc:
            auth_service.verify_code(
                PHONE, code, now=base + timedelta(seconds=auth_service.CODE_TTL_SECONDS + 1)
            )
        assert exc.value.code is ErrorCode.SMS_CODE_EXPIRED

    def test_wrong_code_is_rejected(self, session, settings):
        auth_service.request_code(session, settings, PHONE)
        with pytest.raises(BusinessError) as exc:
            auth_service.verify_code(PHONE, "000000")
        assert exc.value.code is ErrorCode.SMS_CODE_INVALID

    def test_verify_without_request_is_rejected(self, session):
        with pytest.raises(BusinessError) as exc:
            auth_service.verify_code(PHONE, "123456")
        assert exc.value.code is ErrorCode.SMS_CODE_INVALID

    def test_login_creates_account_on_first_use(self, session, settings):
        _, code = auth_service.request_code(session, settings, PHONE)
        tourist = auth_service.login(session, settings, PHONE, code)
        assert tourist.phone == PHONE
        assert tourist.preference_tags == []
        assert tourist.has_preference is False
        assert tourist.last_login_at is not None

    def test_login_twice_reuses_same_account(self, session, settings):
        base = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)
        _, code1 = auth_service.request_code(session, settings, PHONE, now=base)
        first = auth_service.login(session, settings, PHONE, code1, now=base)
        _, code2 = auth_service.request_code(
            session, settings, PHONE, now=base + timedelta(seconds=61)
        )
        second = auth_service.login(
            session, settings, PHONE, code2, now=base + timedelta(seconds=61)
        )
        assert first.id == second.id
        assert len(session.scalars(select(Tourist)).all()) == 1

    def test_code_is_single_use(self, session, settings):
        _, code = auth_service.request_code(session, settings, PHONE)
        auth_service.login(session, settings, PHONE, code)
        with pytest.raises(BusinessError) as exc:
            auth_service.verify_code(PHONE, code)
        assert exc.value.code is ErrorCode.SMS_CODE_INVALID

    def test_too_many_failures_locks_the_phone(self, session, settings):
        base = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)
        auth_service.request_code(session, settings, PHONE, now=base)
        for offset in range(settings.login_max_attempts):
            with pytest.raises(BusinessError) as exc:
                auth_service.login(
                    session, settings, PHONE, "000000", now=base + timedelta(seconds=offset)
                )
            assert exc.value.code is ErrorCode.SMS_CODE_INVALID
        with pytest.raises(BusinessError) as exc:
            auth_service.login(session, settings, PHONE, "000000", now=base + timedelta(seconds=10))
        assert exc.value.code is ErrorCode.RATE_LIMITED

    def test_lock_expires_after_configured_minutes(self, session, settings):
        base = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)
        auth_service.request_code(session, settings, PHONE, now=base)
        for offset in range(settings.login_max_attempts):
            with pytest.raises(BusinessError):
                auth_service.login(
                    session, settings, PHONE, "000000", now=base + timedelta(seconds=offset)
                )
        locked_until = base + timedelta(minutes=settings.login_lock_minutes, seconds=1)
        # 锁定窗口过后重新计数，不再抛 RATE_LIMITED（此时验证码已过期，抛的是 EXPIRED）
        with pytest.raises(BusinessError) as exc:
            auth_service.login(session, settings, PHONE, "000000", now=locked_until)
        assert exc.value.code is ErrorCode.SMS_CODE_EXPIRED

    def test_preference_round_trip_sets_all_four_fields(self, session, settings):
        _, code = auth_service.request_code(session, settings, PHONE)
        tourist = auth_service.login(session, settings, PHONE, code)
        auth_service.save_preferences(
            session,
            tourist,
            tags=["人文历史", "美食"],
            party_type="COUPLE",
            pace="RELAXED",
            budget_level="COMFORT",
        )
        assert tourist.preference_tags == ["人文历史", "美食"]
        assert tourist.party_type == "COUPLE"
        assert tourist.pace == "RELAXED"
        assert tourist.budget_level == "COMFORT"
        assert tourist.has_preference is True

    def test_blank_tags_dropped_and_duplicates_merged(self, session, settings):
        _, code = auth_service.request_code(session, settings, PHONE)
        tourist = auth_service.login(session, settings, PHONE, code)
        auth_service.save_preferences(
            session,
            tourist,
            tags=["  美食 ", "", "美食", "  "],
            party_type="SOLO",
            pace="MODERATE",
            budget_level="ECONOMY",
        )
        assert tourist.preference_tags == ["美食"]

    def test_more_than_six_tags_is_rejected(self, session, settings):
        _, code = auth_service.request_code(session, settings, PHONE)
        tourist = auth_service.login(session, settings, PHONE, code)
        with pytest.raises(BusinessError) as exc:
            auth_service.save_preferences(
                session,
                tourist,
                tags=[f"标签{i}" for i in range(7)],
                party_type="SOLO",
                pace="MODERATE",
                budget_level="ECONOMY",
            )
        assert exc.value.code is ErrorCode.CONDITION_TOO_MANY_TAGS

    def test_broken_json_degrades_to_empty_list(self, session, settings):
        _, code = auth_service.request_code(session, settings, PHONE)
        tourist = auth_service.login(session, settings, PHONE, code)
        tourist.preference_tags_json = "{not json"
        assert tourist.preference_tags == []
        assert tourist.has_preference is False


class TestAuthApi:
    def test_me_returns_null_when_anonymous(self, api_client: TestClient):
        response = api_client.get("/api/auth/me")
        assert response.status_code == 200
        assert response.json()["data"] is None

    def test_login_sets_httponly_cookie(self, api_client: TestClient):
        response = api_client.post("/api/auth/sms-code", json={"phone": PHONE})
        assert response.status_code == 200
        code = response.json()["data"]["debugCode"]

        login = api_client.post("/api/auth/login", json={"phone": PHONE, "code": code})
        assert login.status_code == 200
        # 响应里的手机号必须脱敏，只有库里才是明文
        assert login.json()["data"]["tourist"]["phone"] == "138****8000"

        cookie = login.headers["set-cookie"]
        assert auth_service_token_cookie_name() in cookie
        assert "HttpOnly" in cookie

    def test_me_returns_tourist_after_login(self, api_client: TestClient):
        code = api_client.post("/api/auth/sms-code", json={"phone": PHONE}).json()["data"][
            "debugCode"
        ]
        api_client.post("/api/auth/login", json={"phone": PHONE, "code": code})
        me = api_client.get("/api/auth/me")
        assert me.json()["data"]["phone"] == "138****8000"

    def test_bad_phone_is_400(self, api_client: TestClient):
        response = api_client.post("/api/auth/sms-code", json={"phone": "12345"})
        assert response.status_code == 400
        assert response.json()["code"] == ErrorCode.PARAM_INVALID.value

    def test_preference_is_null_before_any_save(self, api_client: TestClient):
        code = api_client.post("/api/auth/sms-code", json={"phone": PHONE}).json()["data"][
            "debugCode"
        ]
        api_client.post("/api/auth/login", json={"phone": PHONE, "code": code})
        response = api_client.get("/api/tourists/me/preference")
        assert response.status_code == 200
        assert response.json()["data"] is None

    def test_preference_requires_login(self, api_client: TestClient):
        response = api_client.put(
            "/api/tourists/me/preference",
            json={"preferenceTags": ["美食"], "partyType": "SOLO"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == ErrorCode.UNAUTHORIZED.value

    def test_preferences_saved_and_read_back(self, api_client: TestClient):
        code = api_client.post("/api/auth/sms-code", json={"phone": PHONE}).json()["data"][
            "debugCode"
        ]
        api_client.post("/api/auth/login", json={"phone": PHONE, "code": code})
        saved = api_client.put(
            "/api/tourists/me/preference",
            json={
                "preferenceTags": ["人文历史"],
                "partyType": "COUPLE",
                "pace": "RELAXED",
                "budgetLevel": "COMFORT",
            },
        )
        assert saved.status_code == 200
        assert saved.json()["data"]["preferenceTags"] == ["人文历史"]
        assert saved.json()["data"]["partyType"] == "COUPLE"

        read_back = api_client.get("/api/tourists/me/preference")
        assert read_back.json()["data"]["pace"] == "RELAXED"
        assert api_client.get("/api/auth/me").json()["data"]["hasPreference"] is True

    def test_sms_code_alias_is_accepted(self, api_client: TestClient):
        code = api_client.post("/api/auth/sms-code", json={"phone": PHONE}).json()["data"][
            "debugCode"
        ]
        login = api_client.post("/api/auth/login", json={"phone": PHONE, "smsCode": code})
        assert login.status_code == 200

    def test_unknown_party_type_is_400(self, api_client: TestClient):
        code = api_client.post("/api/auth/sms-code", json={"phone": PHONE}).json()["data"][
            "debugCode"
        ]
        api_client.post("/api/auth/login", json={"phone": PHONE, "code": code})
        response = api_client.put(
            "/api/tourists/me/preference",
            json={"preferenceTags": ["美食"], "partyType": "GROUP"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == ErrorCode.PARAM_INVALID.value

    def test_logout_clears_cookie(self, api_client: TestClient):
        code = api_client.post("/api/auth/sms-code", json={"phone": PHONE}).json()["data"][
            "debugCode"
        ]
        api_client.post("/api/auth/login", json={"phone": PHONE, "code": code})
        logout = api_client.post("/api/auth/logout")
        assert logout.status_code == 200
        me = api_client.get("/api/auth/me")
        assert me.json()["data"] is None


def auth_service_token_cookie_name() -> str:
    """Cookie 名从安全模块取，避免测试和实现各写一份字符串。"""
    from app.core.security import ACCESS_TOKEN_COOKIE

    return ACCESS_TOKEN_COOKIE

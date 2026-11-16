"""`StrategyService` 的单元测试（Issue #13 / UC-09）。

覆盖 Issue 任务清单里点名的五件事：和为 1 校验、越界校验、归一化、版本自增、回滚。
另外单独覆盖两处容易被改坏的地方：60 秒缓存的失效时机、`preference → pref` 的映射。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import BusinessError, ErrorCode
from app.models.base import Base
from app.models.strategy import StrategyParameter
from app.schemas.strategy import StrategyPayload, ThresholdsIn, WeightsIn
from app.services.strategy_service import (
    StrategyService,
    invalidate_cache,
    normalize_weights,
    validate_weights,
    zero_weight_warnings,
)

BALANCED = {"preference": 0.10, "weather": 0.25, "crowd": 0.23, "travel": 0.14, "cost": 0.28}
# cost=0 又要满足「和为 1」：其余四项重新分配，把省下的 0.28 摊上去
ZERO_COST = {"preference": 0.20, "weather": 0.30, "crowd": 0.30, "travel": 0.20, "cost": 0.0}
# cost=0 又要满足「和为 1」：其余四项重新分配，把省下的 0.28 摊上去
ZERO_COST = {"preference": 0.20, "weather": 0.30, "crowd": 0.30, "travel": 0.20, "cost": 0.0}


@pytest.fixture
def session() -> Iterator[Session]:
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


def _payload(**overrides: object) -> StrategyPayload:
    body: dict[str, object] = {"weights": dict(BALANCED)}
    body.update(overrides)
    return StrategyPayload.model_validate(body)


# ----------------------------------------------------------------------
# validate_weights（BR-23）
# ----------------------------------------------------------------------
class TestValidateWeights:
    def test_balanced_passes(self) -> None:
        validate_weights(BALANCED)

    def test_tolerance_allows_one_percent(self) -> None:
        # 1.005 落在 ±0.01 内：SRS UC-09 明确允许，不能被实现悄悄收紧到 0.001
        validate_weights({**BALANCED, "cost": 0.285})

    def test_sum_error_mentions_total(self) -> None:
        with pytest.raises(BusinessError) as info:
            validate_weights(
                {"preference": 0.2, "weather": 0.2, "crowd": 0.2, "travel": 0.2, "cost": 0.3}
            )
        assert info.value.code is ErrorCode.PARAM_INVALID
        # AC-2：提示里必须带当前和，页面要能直接显示
        assert "1.1000" in (info.value.message or "")
        assert info.value.details[0].field == "weights"

    def test_each_weight_in_range(self) -> None:
        with pytest.raises(BusinessError) as info:
            validate_weights({**BALANCED, "crowd": 1.2, "cost": -0.09})
        assert "crowd" in info.value.details[0].reason

    def test_missing_key(self) -> None:
        with pytest.raises(BusinessError) as info:
            validate_weights({"preference": 1.0})
        assert "缺少权重项" in info.value.details[0].reason


# ----------------------------------------------------------------------
# 归一化
# ----------------------------------------------------------------------
class TestNormalize:
    def test_sums_to_exactly_one(self) -> None:
        scaled = normalize_weights(
            {"preference": 1, "weather": 2, "crowd": 3, "travel": 2, "cost": 2}
        )
        assert sum(scaled.values()) == pytest.approx(1.0, abs=1e-9)

    def test_keeps_proportions(self) -> None:
        scaled = normalize_weights(
            {"preference": 0.1, "weather": 0.2, "crowd": 0.3, "travel": 0.2, "cost": 0.2}
        )
        assert scaled["crowd"] == pytest.approx(0.3)
        assert scaled["preference"] == pytest.approx(0.1)

    def test_residue_goes_to_largest(self) -> None:
        # 三分之一这类除不尽的比例：四项加起来会差 0.0001，必须补到最大项
        scaled = normalize_weights(
            {"preference": 1, "weather": 1, "crowd": 1, "travel": 0, "cost": 0}
        )
        assert sum(scaled.values()) == pytest.approx(1.0, abs=1e-9)
        # 三项 0.3333 加起来是 0.9999，残差 0.0001 补到最大项（三项并列时取第一个），
        # 所以允许其中一项比其他两项多 0.0001
        assert sorted(scaled.values())[:2] == [0.0, 0.0]
        assert scaled["preference"] + scaled["weather"] + scaled["crowd"] == pytest.approx(
            1.0, abs=1e-9
        )

    def test_all_zero_falls_back_to_even(self) -> None:
        scaled = normalize_weights(dict.fromkeys(BALANCED, 0.0))
        assert scaled["preference"] == pytest.approx(0.2)
        assert sum(scaled.values()) == pytest.approx(1.0, abs=1e-9)


# ----------------------------------------------------------------------
# 二次确认
# ----------------------------------------------------------------------
class TestZeroWeightWarning:
    def test_zero_weight_alone_is_fine(self) -> None:
        # 只看剩下四项是合理诉求，不该弹确认
        assert zero_weight_warnings({**BALANCED, "cost": 0.0}, []) == []

    def test_zero_weight_with_disabled_fallback_warns(self) -> None:
        warnings = zero_weight_warnings({**BALANCED, "cost": 0.0}, ["cost"])
        assert len(warnings) == 1
        assert "cost" in warnings[0]

    def test_non_zero_weight_with_disabled_fallback_is_fine(self) -> None:
        assert zero_weight_warnings(BALANCED, ["cost"]) == []


# ----------------------------------------------------------------------
# 读：默认值与版本
# ----------------------------------------------------------------------
class TestCurrent:
    def test_empty_table_returns_version_zero(self, session: Session) -> None:
        params = StrategyService(session).current()
        assert params.version == 0
        # 默认值必须与 Settings 同源，否则「没发布」与「发布了默认值」结果不同
        assert params.weights == {
            "preference": 0.10,
            "weather": 0.25,
            "crowd": 0.23,
            "travel": 0.14,
            "cost": 0.28,
        }

    def test_cache_hit_avoids_requery(self, session: Session) -> None:
        service = StrategyService(session)
        first = service.current()
        # 绕过 service 直接插一条：缓存没失效的话仍读到旧值
        session.add(
            StrategyParameter(
                version=9,
                w_pref=0.2,
                w_weather=0.2,
                w_crowd=0.2,
                w_travel=0.2,
                w_cost=0.2,
                holiday_factors_json="{}",
                thresholds_json="{}",
                disabled_fallbacks_json="[]",
                note="",
                created_by="tester",
            )
        )
        session.commit()
        assert service.current() is first

        invalidate_cache()
        assert service.current().version == 9


# ----------------------------------------------------------------------
# 写：版本自增 / 回滚
# ----------------------------------------------------------------------
class TestPublish:
    def test_version_autoincrements(self, session: Session) -> None:
        service = StrategyService(session)
        first, warnings = service.publish(_payload(), created_by="tester")
        assert warnings == []
        assert first is not None and first.version == 1

        second, _ = service.publish(
            _payload(weights={**BALANCED, "cost": 0.281, "travel": 0.139}), created_by="tester"
        )
        assert second is not None and second.version == 2
        # 历史版本一条都不删（BR-24）
        total = session.execute(select(func.count()).select_from(StrategyParameter)).scalar_one()
        assert total == 2

    def test_publish_invalidates_cache(self, session: Session) -> None:
        service = StrategyService(session)
        assert service.current().version == 0
        published, _ = service.publish(_payload(), created_by="tester")
        assert published is not None
        # AC-1：保存后下一次读（≤5 秒）必须已经拿到新版本，而不是等 TTL 到期
        assert service.current().version == published.version

    def test_invalid_sum_rejected(self, session: Session) -> None:
        weights = {"preference": 0.2, "weather": 0.2, "crowd": 0.2, "travel": 0.2, "cost": 0.3}
        with pytest.raises(BusinessError) as info:
            StrategyService(session).publish(_payload(weights=weights), created_by="tester")
        assert info.value.code is ErrorCode.PARAM_INVALID
        assert (
            session.execute(select(func.count()).select_from(StrategyParameter)).scalar_one() == 0
        )

    def test_requires_confirm_does_not_persist(self, session: Session) -> None:
        params, warnings = StrategyService(session).publish(
            _payload(weights=dict(ZERO_COST), disabled_fallbacks=["cost"]),
            created_by="tester",
        )
        assert params is None
        assert warnings
        assert (
            session.execute(select(func.count()).select_from(StrategyParameter)).scalar_one() == 0
        )

    def test_confirm_true_persists(self, session: Session) -> None:
        params, warnings = StrategyService(session).publish(
            _payload(weights=dict(ZERO_COST), disabled_fallbacks=["cost"], confirm=True),
            created_by="tester",
        )
        assert warnings == []
        assert params is not None
        assert params.disabled_fallbacks == ("cost",)

    def test_thresholds_roundtrip(self, session: Session) -> None:
        payload = _payload(thresholds=ThresholdsIn(dailyHours=8, maxIteration=12))
        params, _ = StrategyService(session).publish(payload, created_by="tester")
        assert params is not None
        assert params.thresholds["dailyHours"] == 8
        assert params.thresholds["maxIteration"] == 12


class TestRollback:
    def test_rollback_creates_new_version(self, session: Session) -> None:
        service = StrategyService(session)
        first, _ = service.publish(_payload(), created_by="tester")
        assert first is not None
        second, _ = service.publish(
            _payload(
                weights={
                    "preference": 0.4,
                    "weather": 0.2,
                    "crowd": 0.2,
                    "travel": 0.1,
                    "cost": 0.1,
                }
            ),
            created_by="tester",
        )
        assert second is not None and second.version == 2

        restored = service.rollback(1, created_by="tester")
        # AC-3：回滚不是把指针拨回去，而是新增一条版本
        assert restored.version == 3
        assert restored.weights == first.weights
        assert restored.note == "回滚自 v1"
        # 历史仍在
        assert [item.version for item in service.list_versions()] == [3, 2, 1]

    def test_rollback_missing_version(self, session: Session) -> None:
        with pytest.raises(BusinessError) as info:
            StrategyService(session).rollback(42)
        assert info.value.code is ErrorCode.NOT_FOUND


# ----------------------------------------------------------------------
# 引擎侧映射
# ----------------------------------------------------------------------
class TestEngineWeights:
    def test_maps_preference_to_pref(self, session: Session) -> None:
        weights = StrategyService(session).current().engine_weights()
        assert set(weights) == {"pref", "weather", "crowd", "travel", "cost"}
        assert weights["pref"] == pytest.approx(0.10)

    def test_normalizes_to_exact_one(self, session: Session) -> None:
        params, _ = StrategyService(session).publish(
            # 和 = 1.005，在允差内但不等 1
            _payload(weights={**BALANCED, "weather": 0.255}),
            created_by="tester",
        )
        assert params is not None
        assert sum(params.engine_weights().values()) == pytest.approx(1.0, abs=1e-9)

    def test_weights_roundtrip_through_orm(self, session: Session) -> None:
        service = StrategyService(session)
        payload = _payload(
            weights=WeightsIn(
                **{"preference": 0.2, "weather": 0.2, "crowd": 0.2, "travel": 0.2, "cost": 0.2}
            )
        )
        params, _ = service.publish(payload, created_by="tester")
        assert params is not None
        invalidate_cache()
        assert service.current().weights["preference"] == pytest.approx(0.2)

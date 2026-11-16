"""排程引擎纯函数单元测试（Issue #41）。

只覆盖无外部依赖的纯函数：cost_ratio / crowd_penalty / Weights 校验 /
calculate_crowd_index。不碰数据库、HTTP、时间。
"""

from __future__ import annotations

import pytest

from app.engine.crowd import calculate_crowd_index
from app.engine.scorer import Weights, cost_ratio, crowd_penalty
from app.engine.selector import Poi


def _poi(price: float = 50.0, capacity: int = 100) -> Poi:
    return Poi(
        id=1,
        name="西湖",
        city="杭州",
        category="outdoor",
        lat=30.0,
        lng=120.0,
        open_time="08:00",
        close_time="18:00",
        price=price,
        capacity=capacity,
        tags=(),
        status="PUBLISHED",
    )


# ---------- cost_ratio ----------


def test_cost_ratio_normal():
    assert cost_ratio(_poi(price=50), budget=100) == pytest.approx(0.5)


def test_cost_ratio_budget_zero_returns_worst():
    # budget<=0 时返回 1.0（最差分），避免除零
    assert cost_ratio(_poi(price=50), budget=0) == 1.0


def test_cost_ratio_clamped_to_one():
    # 门票超过预算，截断到 1.0
    assert cost_ratio(_poi(price=250), budget=100) == 1.0


# ---------- crowd_penalty ----------


def test_crowd_penalty_missing_is_neutral():
    # 数据缺失给中性 0.5，而不是 0（不奖励没有数据的 POI）
    assert crowd_penalty(None) == 0.5


def test_crowd_penalty_bounds():
    assert crowd_penalty(0) == 0.0
    assert crowd_penalty(100) == 1.0
    assert crowd_penalty(50) == pytest.approx(0.5)


# ---------- Weights 校验 ----------


def test_weights_sum_must_be_one():
    with pytest.raises(ValueError, match="之和"):
        Weights(pref=0.2, weather=0.2, crowd=0.2, travel=0.2, cost=0.3)


def test_weights_each_in_range():
    with pytest.raises(ValueError, match="必须在"):
        Weights(pref=1.5, weather=0.2, crowd=0.2, travel=0.2, cost=-0.1)


def test_weights_valid_passes():
    w = Weights(pref=0.1, weather=0.25, crowd=0.23, travel=0.14, cost=0.28)
    assert abs(w.pref + w.weather + w.crowd + w.travel + w.cost - 1.0) < 0.001


# ---------- calculate_crowd_index ----------


def test_crowd_index_missing_data():
    assert calculate_crowd_index(None, 100) is None
    assert calculate_crowd_index(50, 0) is None  # capacity<=0 视为数据缺失


def test_crowd_index_bounds_and_rounding():
    assert calculate_crowd_index(0, 100) == 0
    assert calculate_crowd_index(150, 100) == 100  # 超出截断
    assert calculate_crowd_index(50, 100) == 50

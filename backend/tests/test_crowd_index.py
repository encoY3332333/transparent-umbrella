"""拥挤度公式测试（Issue #5）。"""

from __future__ import annotations

import pytest

from app.engine.crowd import CrowdIndexCalculator, apply_crowd_index, calculate_crowd_index
from app.engine.selector import Poi


@pytest.mark.parametrize(
    ("volume", "capacity", "expected"),
    [
        (0, 1000, 0),
        (500, 1000, 50),
        (800, 1000, 80),
        (1000, 1000, 100),
        (2000, 1000, 100),
        (-1, 1000, 0),
        (None, 1000, None),
        (500, 0, None),
        (500, -1, None),
    ],
)
def test_calculate_crowd_index(volume: int | None, capacity: int, expected: int | None) -> None:
    assert calculate_crowd_index(volume, capacity) == expected
    assert CrowdIndexCalculator.calculate(volume, capacity) == expected


def test_apply_crowd_index_marks_missing_as_unknown() -> None:
    poi = Poi(
        id=1,
        name="POI-1",
        city="西安",
        category="INDOOR",
        lat=34.0,
        lng=108.0,
        open_time="09:00",
        close_time="18:00",
        price=0.0,
        capacity=1000,
        tags=("人文历史",),
        status="PUBLISHED",
    )

    [known] = apply_crowd_index([poi], {1: 500})
    [unknown] = apply_crowd_index([poi], {})

    assert known.crowd_index == 50
    assert unknown.crowd_index is None

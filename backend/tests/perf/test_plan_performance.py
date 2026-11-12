"""性能基线（Issue #14 · NFR-P1）。

200 个候选 POI、7 天行程，P95 ≤ 10 秒（不含外部接口——引擎本身不触网，
通勤矩阵由调用方传入，符合「不含外部接口」的口径）。

为什么取 5 次中位数而不是单次断言：
CI 机器性能波动大，单次绝对耗时必然 flaky。中位数对偶发的慢运行有韧性，
且失败时打印全部 5 次耗时，方便判断是「整体变慢」还是「一次抖动」。

标记 `@pytest.mark.perf`：PR 上不跑（见 ci.yml 的 perf job 条件），
只在 main 与 workflow_dispatch 上执行。
"""

from __future__ import annotations

import random
import statistics
import time
from datetime import date

import pytest

from app.engine.scorer import TouristProfile
from app.engine.selector import Candidate, Poi
from app.engine.strategy_engine import PlanRequest, StrategyEngine

DAY = date(2026, 12, 1)

N_POIS = 200
N_DAYS = 7
RUNS = 5
LIMIT_SECONDS = 10.0

_CATEGORIES = ("INDOOR", "OUTDOOR", "NATURE", "SCENIC")
_TAGS = ("人文历史", "自然风光", "美食", "亲子", "夜游")
_PRICES = (0.0, 30.0, 60.0, 120.0, 180.0)
_OPEN = ("08:00", "09:00", "10:00")
_CLOSE = ("17:00", "18:00", "20:00", "22:00")


def _build_pool(seed: int) -> list[Candidate]:
    """构造 200 个候选：类别/价位/营业时间/拥挤度都带随机性，覆盖各约束分支。"""
    rng = random.Random(seed)
    pois = []
    for i in range(1, N_POIS + 1):
        pois.append(
            Poi(
                id=i,
                name=f"POI-{i}",
                city="西安",
                category=rng.choice(_CATEGORIES),
                lat=34.2 + rng.random() * 0.3,
                lng=108.9 + rng.random() * 0.3,
                open_time=rng.choice(_OPEN),
                close_time=rng.choice(_CLOSE),
                price=rng.choice(_PRICES),
                capacity=rng.randint(500, 9000),
                tags=tuple(rng.sample(_TAGS, 2)),
                status="PUBLISHED",
            )
        )
    return [Candidate(poi=p, crowd_index=rng.randint(0, 100)) for p in pois]


@pytest.mark.perf
def test_plan_200_pois_7_days_median_under_10s() -> None:
    candidates = _build_pool(seed=2026)
    tourist = TouristProfile(preference_tags=frozenset({"人文历史", "美食"}), budget=6000.0)
    request = PlanRequest(
        start_date=DAY,
        days=N_DAYS,
        tourist=tourist,
        weather_by_day={None: "CLEAR"},
    )
    engine = StrategyEngine()

    durations: list[float] = []
    plans: list = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        plans = engine.plan(candidates, request)
        durations.append(time.perf_counter() - t0)

    median = statistics.median(durations)
    print(
        f"\n性能基线：{N_POIS} POI × {N_DAYS} 天 × {RUNS} 次，"
        f"各次 {[round(d, 3) for d in durations]}s，中位数 {median:.3f}s（阈值 {LIMIT_SECONDS}s）"
    )

    # 顺带确认功能没退化：方案数在 [1,3]，每天有活动
    assert 1 <= len(plans) <= 3
    assert plans[0].days[0].activity_count >= 1

    assert median <= LIMIT_SECONDS, (
        f"中位数 {median:.3f}s 超过 {LIMIT_SECONDS}s；全部耗时 {[round(d, 3) for d in durations]}"
    )

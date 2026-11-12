"""拥挤度计算（Issue #5）。

公式来自 SRS 3.3.3：
    CrowdIndex(p, d) = min(100, round(100 * HistVolume(p, d) / Capacity(p)))
数据缺失或承载量非正时返回 `None`，由排程层标记为 `UNKNOWN`，不施加拥挤度惩罚。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.engine.selector import Candidate, Poi


def calculate_crowd_index(volume: int | None, capacity: int) -> int | None:
    """返回 [0, 100] 的整数；无法计算时返回 None。"""
    if volume is None or capacity <= 0:
        return None
    if volume <= 0:
        return 0
    return min(100, round(100 * volume / capacity))


class CrowdIndexCalculator:
    """保留类接口，方便 #6 注入/替换；实现委托给纯函数。"""

    @staticmethod
    def calculate(volume: int | None, capacity: int) -> int | None:
        return calculate_crowd_index(volume, capacity)


def apply_crowd_index(
    pois: Iterable[Poi],
    volumes: Mapping[int, int],
) -> list[Candidate]:
    """把批量人流量映射到 POI；缺失的 POI 标记为 None（UNKNOWN）。"""
    return [
        Candidate(
            poi=poi,
            crowd_index=calculate_crowd_index(volumes.get(poi.id), poi.capacity),
        )
        for poi in pois
    ]

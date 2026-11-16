"""拥挤度计算（Issue #5）。

公式来自 SRS 3.3.3：
    CrowdIndex(p, d) = min(100, round(100 * HistVolume(p, d) / Capacity(p)))
数据缺失或承载量非正时返回 `None`；`Candidate.crowd_known=False` 表示
“未知风险”，由评分层按中性值处理，不能当成“不拥挤”。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping

from app.engine.selector import Candidate, Poi

logger = logging.getLogger(__name__)


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
    result: list[Candidate] = []
    for poi in pois:
        if poi.capacity <= 0:
            logger.warning(
                "POI %s capacity=%s，拥挤度无法计算，按 UNKNOWN 处理", poi.id, poi.capacity
            )
        volume = volumes.get(poi.id)
        result.append(
            Candidate(
                poi=poi,
                crowd_index=CrowdIndexCalculator.calculate(volume, poi.capacity),
                crowd_known=poi.capacity > 0 and volume is not None,
            )
        )
    return result

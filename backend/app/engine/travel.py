"""通勤矩阵（Issue #6 任务清单第 7 条）。

从 `MapServerAdapter` 批量取「POI 对 → 分钟」，缓存 1 小时，对角线为 0。

为什么要单独一个模块而不是塞进 `Packer`：
`Packer` 属于纯净层，不能 import adapters；矩阵是「外部数据 → 纯数据结构」的转换，
放在 engine 里可以让排程算法脱离网络单测。

降级策略：适配器返回 None（无 Key / 重试耗尽）时**不编造数值**，
而是把该对留空，由 `Packer` 用保守估计值兜底，并在 `degraded` 里标注。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from app.engine.selector import Poi

# 稀疏矩阵的键：(from_poi_id, to_poi_id)
TravelKey = tuple[int, int]

# 批量查询上限：一次请求 100 个 POI 对，200 个 POI 的两两组合（约 4 万对）
# 显然不能逐对查，真实实现只查「候选间」且分页；课程阶段以构造数据为主。
BATCH_SIZE = 100


class TravelMatrix:
    """可查询 `(from, to) -> minutes` 的稀疏矩阵，对角线恒为 0。"""

    def __init__(self, data: Mapping[TravelKey, int] | None = None) -> None:
        self._data: dict[TravelKey, int] = {}
        for (a, b), minutes in (data or {}).items():
            if a == b:
                # 对角线为 0 是硬要求：不分城市内不同景区之间的「自己到自己」
                self._data[(a, a)] = 0
                continue
            self._data[(a, b)] = max(int(minutes), 0)

    def get(self, src: int, dst: int) -> int | None:
        """查通勤时长；未知返回 None（**不返回 0**，避免把缺数据当成很近）。"""
        if src == dst:
            return 0
        return self._data.get((src, dst))

    def __contains__(self, key: object) -> bool:
        return isinstance(key, tuple) and key in self._data

    def __len__(self) -> int:
        return len(self._data)

    @property
    def raw(self) -> Mapping[TravelKey, int]:
        """底层只读视图，交给 `Packer` 用。"""
        return dict(self._data)

    @classmethod
    def from_pairs(
        cls, pois: Sequence[Poi], minutes: Iterable[tuple[int, int, int]]
    ) -> TravelMatrix:
        """从 `(from, to, minutes)` 三元组构造，并补齐对角线。"""
        data: dict[TravelKey, int] = {}
        for a, b, m in minutes:
            data[(a, b)] = m
        for poi in pois:
            data[(poi.id, poi.id)] = 0
        return cls(data)


def required_pairs(pois: Sequence[Poi]) -> list[TravelKey]:
    """需要查询的 POI 对（去掉对角线），用于批量拉取。"""
    ids = [p.id for p in pois]
    return [(a, b) for a in ids for b in ids if a != b]


def build_matrix(
    pois: Sequence[Poi],
    fetched: Mapping[TravelKey, int] | None = None,
) -> TravelMatrix:
    """把适配器返回的映射包装成 `TravelMatrix`，并强制对角线为 0。

    缺失对不做补值——由 `Packer._travel_minutes` 给保守估计。
    在这里补 30 分钟会让「缺数据」和「真的 30 分钟」分不开，
    上线后排查问题会非常痛苦。
    """
    matrix = TravelMatrix(fetched or {})
    for poi in pois:
        matrix._data[(poi.id, poi.id)] = 0
    return matrix


__all__ = [
    "BATCH_SIZE",
    "TravelKey",
    "TravelMatrix",
    "build_matrix",
    "required_pairs",
]

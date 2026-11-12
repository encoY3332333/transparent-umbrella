"""候选 POI 筛选（Issue #5）。

**纯净层**：只依赖标准库与本包 dataclass，不 import adapters / models / SQLAlchemy。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


class PoiSelectionError(Exception):
    """候选集无法满足业务约束。"""


class InsufficientPoiData(PoiSelectionError):
    """放宽后候选仍不足最低数量。"""

    def __init__(self, city: str, count: int, minimum: int) -> None:
        self.city = city
        self.count = count
        self.minimum = minimum
        super().__init__(f"{city}: 候选 POI 仅 {count} 个，低于最低要求 {minimum}")


@dataclass(frozen=True)
class Poi:
    """排程所需的最小 POI 视图，不绑定数据库模型。"""

    id: int
    name: str
    city: str
    category: str
    lat: float
    lng: float
    open_time: str
    close_time: str
    price: float
    capacity: int
    tags: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class SelectionCriteria:
    """候选筛选条件；由 service 从 TravelCondition 转换而来。"""

    city: str
    preference_tags: tuple[str, ...] = ()
    must_visit: tuple[int, ...] = ()
    avoid_poi: tuple[int, ...] = ()
    min_candidates: int = 20
    max_candidates: int = 300

    def __post_init__(self) -> None:
        if self.min_candidates < 1:
            raise ValueError("min_candidates 必须 >= 1")
        if self.max_candidates < self.min_candidates:
            raise ValueError("max_candidates 不能小于 min_candidates")


@dataclass(frozen=True)
class Candidate:
    """带拥挤度的候选 POI；crowd_index 为 None 表示数据源降级。"""

    poi: Poi
    crowd_index: int | None = None


def _normalize_city(city: str) -> str:
    return city.strip().removesuffix("市")


def _dedupe(pois: Iterable[Poi]) -> list[Poi]:
    seen: set[int] = set()
    result: list[Poi] = []
    for poi in pois:
        if poi.id in seen:
            continue
        seen.add(poi.id)
        result.append(poi)
    return result


class CandidateSelector:
    """按城市、状态、偏好、必去/必避筛选候选 POI。"""

    def select(
        self,
        criteria: SelectionCriteria,
        pois: Iterable[Poi],
    ) -> list[Poi]:
        """返回按“必去优先、标签命中优先”排序的候选集。

        放宽顺序严格限定为：先补同城 PUBLISHED 的非标签 POI；
        **不放宽** 城市、PUBLISHED、必避清单。仍不足则抛 `InsufficientPoiData`。
        """
        avoid = set(criteria.avoid_poi)
        must = set(criteria.must_visit)
        overlap = must & avoid
        if overlap:
            raise PoiSelectionError(f"必去与必避冲突: {sorted(overlap)}")

        city = _normalize_city(criteria.city)
        published = [
            poi
            for poi in pois
            if poi.status == "PUBLISHED"
            and _normalize_city(poi.city) == city
            and poi.id not in avoid
        ]
        if not published:
            raise InsufficientPoiData(city, 0, criteria.min_candidates)

        tags = set(criteria.preference_tags)
        must_pois = [poi for poi in published if poi.id in must]
        tagged = [poi for poi in published if not tags or bool(set(poi.tags) & tags)]

        selected = _dedupe(must_pois + tagged)
        if len(selected) < criteria.min_candidates:
            selected = _dedupe(selected + published)

        if len(selected) < criteria.min_candidates:
            raise InsufficientPoiData(city, len(selected), criteria.min_candidates)

        selected.sort(
            key=lambda poi: (
                0 if poi.id in must else 1,
                0 if tags and set(poi.tags) & tags else 1,
                poi.id,
            )
        )

        if len(selected) > criteria.max_candidates:
            selected = selected[: criteria.max_candidates]

        return selected

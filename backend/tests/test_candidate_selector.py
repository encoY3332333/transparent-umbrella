"""候选 POI 筛选测试（Issue #5）。"""

from __future__ import annotations

import pytest

from app.engine.selector import (
    CandidateSelector,
    InsufficientPoiData,
    Poi,
    PoiSelectionError,
    SelectionCriteria,
)


def make_poi(
    poi_id: int,
    *,
    city: str = "西安",
    tags: tuple[str, ...] = ("人文历史",),
    status: str = "PUBLISHED",
    capacity: int = 1000,
) -> Poi:
    return Poi(
        id=poi_id,
        name=f"POI-{poi_id}",
        city=city,
        category="INDOOR",
        lat=34.0,
        lng=108.0,
        open_time="09:00",
        close_time="18:00",
        price=0.0,
        capacity=capacity,
        tags=tags,
        status=status,
    )


def test_select_keeps_must_and_excludes_avoid() -> None:
    pois = [make_poi(i, tags=("人文历史",) if i % 2 else ("美食",)) for i in range(1, 27)]
    criteria = SelectionCriteria(
        city="西安市",
        preference_tags=("人文历史",),
        must_visit=(1,),
        avoid_poi=(2,),
    )

    selected = CandidateSelector().select(criteria, pois)

    ids = [poi.id for poi in selected]
    assert len(selected) == 25
    assert 1 in ids
    assert 2 not in ids
    assert ids[0] == 1


def test_select_excludes_non_published() -> None:
    pois = [make_poi(i) for i in range(1, 21)]
    pois.append(make_poi(21, status="DRAFT"))
    pois.append(make_poi(22, status="INACTIVE"))
    criteria = SelectionCriteria(city="西安")

    selected = CandidateSelector().select(criteria, pois)
    ids = {poi.id for poi in selected}

    assert 21 not in ids
    assert 22 not in ids
    assert len(selected) == 20


def test_select_relaxes_tags_when_too_few_matches() -> None:
    pois = [make_poi(i, tags=("人文历史",) if i <= 3 else ("美食",)) for i in range(1, 26)]
    criteria = SelectionCriteria(city="西安", preference_tags=("人文历史",))

    selected = CandidateSelector().select(criteria, pois)

    assert len(selected) == 25
    assert {poi.id for poi in selected} == set(range(1, 26))


def test_select_raises_when_relaxation_still_insufficient() -> None:
    pois = [make_poi(i) for i in range(1, 11)]
    criteria = SelectionCriteria(city="西安", min_candidates=20)

    with pytest.raises(InsufficientPoiData) as exc_info:
        CandidateSelector().select(criteria, pois)

    assert exc_info.value.count == 10
    assert exc_info.value.minimum == 20


def test_select_caps_at_max_but_keeps_must_visit() -> None:
    pois = [make_poi(i) for i in range(1, 351)]
    criteria = SelectionCriteria(
        city="西安",
        must_visit=(350,),
        min_candidates=20,
        max_candidates=300,
    )

    selected = CandidateSelector().select(criteria, pois)
    ids = {poi.id for poi in selected}

    assert len(selected) == 300
    assert 350 in ids


def test_select_rejects_must_avoid_overlap() -> None:
    criteria = SelectionCriteria(city="西安", must_visit=(1,), avoid_poi=(1,))

    with pytest.raises(PoiSelectionError):
        CandidateSelector().select(criteria, [make_poi(1)])

"""人流量适配器测试（Issue #5）。"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from app.adapters.traffic import TrafficServerAdapter
from app.core.config import Settings

DATE_RANGE = (date(2026, 12, 1), date(2026, 12, 3))


def make_adapter(*, api_key: str = "test-key") -> TrafficServerAdapter:
    settings = Settings(
        traffic_api_key=api_key,
        traffic_base_url="https://traffic.test",
        external_max_retries=0,
    )
    return TrafficServerAdapter(
        base_url=settings.traffic_base_url,
        api_key=api_key,
        settings=settings,
    )


def test_adapter_batches_200_pois_into_four_requests(monkeypatch: Any) -> None:
    adapter = make_adapter()
    calls: list[dict[str, str]] = []

    async def fake_get_json(
        path: str,
        params: dict[str, str] | None = None,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        assert path == "/traffic/historical"
        assert params is not None
        calls.append(params)
        ids = [int(value) for value in params["poiIds"].split(",")]
        return {"data": {str(poi_id): 500 for poi_id in ids}}

    monkeypatch.setattr(adapter, "get_json", fake_get_json)
    volumes = asyncio.run(adapter.get_historical_volume(list(range(1, 201)), DATE_RANGE))
    asyncio.run(adapter.aclose())

    assert len(calls) == 4
    assert len(volumes) == 200
    assert volumes[1] == 500
    assert adapter.cache_ttl_seconds == 24 * 60 * 60


def test_adapter_without_key_degrades() -> None:
    adapter = make_adapter(api_key="")
    volumes = asyncio.run(adapter.get_historical_volume([1, 2], DATE_RANGE))
    asyncio.run(adapter.aclose())

    assert volumes == {}
    assert adapter.degraded is True


def test_adapter_parses_list_payload(monkeypatch: Any) -> None:
    adapter = make_adapter()

    async def fake_get_json(
        path: str,
        params: dict[str, str] | None = None,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        return {"data": [{"poiId": 1, "volume": 800}, {"poiId": 2, "volume": 1200}]}

    monkeypatch.setattr(adapter, "get_json", fake_get_json)
    volumes = asyncio.run(adapter.get_historical_volume([1, 2], DATE_RANGE))
    asyncio.run(adapter.aclose())

    assert volumes == {1: 800, 2: 1200}

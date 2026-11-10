"""BaseAdapter：降级、重试、缓存、调用计数。

这几个行为决定「外部系统挂了，行程还能不能生成」，比任何单个适配器实现都重要。
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.adapters.base import BaseAdapter
from app.core.config import Settings

BASE_URL = "https://example.test/api"


def make_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "external_max_retries": 1,
        "external_connect_timeout": 0.5,
        "external_read_timeout": 0.5,
        "cache_ttl_seconds": 60,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def make_adapter(
    handler: Any,
    *,
    api_key: str = "test-key",
    settings: Settings | None = None,
) -> tuple[BaseAdapter, httpx.AsyncClient]:
    client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    adapter = BaseAdapter(
        base_url=BASE_URL,
        api_key=api_key,
        settings=settings or make_settings(),
        client=client,
    )
    return adapter, client


def test_unconfigured_key_degrades_without_calling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("没有 Key 时不允许发起请求")

    adapter, client = make_adapter(handler, api_key="")

    async def scenario() -> None:
        assert adapter.available is False
        assert await adapter.get_json("/weather") is None
        await client.aclose()

    asyncio.run(scenario())
    assert adapter.degraded is True
    assert adapter.calls == 0


def test_successful_response_is_cached() -> None:
    hits = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        hits["count"] += 1
        return httpx.Response(200, json={"temp": 9})

    adapter, client = make_adapter(handler)

    async def scenario() -> None:
        first = await adapter.get_json("/weather", {"city": "西安"})
        second = await adapter.get_json("/weather", {"city": "西安"})
        await client.aclose()

        assert first == {"temp": 9}
        assert second == {"temp": 9}

    asyncio.run(scenario())
    assert hits["count"] == 1, "第二次应命中缓存，不应再打外部接口"
    assert adapter.calls == 1
    assert adapter.degraded is False


def test_retries_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json={"ok": True})

    adapter, client = make_adapter(handler)

    async def scenario() -> None:
        result = await adapter.get_json("/traffic")
        await client.aclose()
        assert result == {"ok": True}

    asyncio.run(scenario())
    assert adapter.calls == 2
    assert adapter.degraded is False


def test_gives_up_and_degrades_after_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    settings = make_settings(external_max_retries=1)
    adapter, client = make_adapter(handler, settings=settings)

    async def scenario() -> None:
        assert await adapter.get_json("/hotel") is None
        await client.aclose()

    asyncio.run(scenario())
    assert adapter.calls == 2
    assert adapter.degraded is True


def test_non_object_payload_degrades() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    adapter, client = make_adapter(handler)

    async def scenario() -> None:
        assert await adapter.get_json("/event") is None
        await client.aclose()

    asyncio.run(scenario())
    assert adapter.degraded is True


def test_network_error_is_swallowed_as_degradation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    adapter, client = make_adapter(handler)

    async def scenario() -> None:
        assert await adapter.get_json("/map") is None
        await client.aclose()

    asyncio.run(scenario())
    assert adapter.degraded is True


def test_cache_key_is_order_insensitive() -> None:
    left = BaseAdapter.cache_key("/traffic", {"city": "西安", "page": 1})
    right = BaseAdapter.cache_key("/traffic", {"page": 1, "city": "西安"})

    assert left == right


def test_auth_params_carries_key() -> None:
    adapter, client = make_adapter(lambda request: httpx.Response(200, json={}))

    assert adapter.auth_params() == {"key": "test-key"}
    asyncio.run(client.aclose())

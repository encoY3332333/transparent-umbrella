"""外部系统代理基类。

所有外部调用都必须继承 `BaseAdapter`，统一获得：超时、重试、TTL 缓存、
降级标记与调用计数。**service 层禁止直接 import httpx**（architecture.md 分层约束第 4 条）。

为什么要这一层：7 个外部系统的超时口径不一致时，行程生成 P95 直接失控；
而把「没配 Key 就降级」写在一个地方，才可能保证 `degraded[]` 的语义一致。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from typing import Any, ClassVar

import httpx
from cachetools import TTLCache

from app.core.config import Settings

logger = logging.getLogger(__name__)

QueryParams = Mapping[str, str | int | float | None]


class BaseAdapter:
    """外部系统的 HTTP 代理。子类只需覆写 `name` 与 `auth_params()`。"""

    name: ClassVar[str] = "base"
    cache_maxsize: ClassVar[int] = 512

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._cache: TTLCache[str, Any] = TTLCache(
            maxsize=self.cache_maxsize, ttl=max(settings.cache_ttl_seconds, 1)
        )
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(
                connect=settings.external_connect_timeout,
                read=settings.external_read_timeout,
                write=settings.external_read_timeout,
                pool=settings.external_connect_timeout,
            ),
        )
        # 本次流程内的调用次数，用于 BR-10（单次规划 ≤ 60 次）计数
        self.calls = 0
        # 一旦降级就置位，由 PlanService 汇总进响应的 degraded[]
        self.degraded = False

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """没配 API Key 就视为「该外部系统不可用」，走降级而不是报错。"""
        return bool(self._api_key)

    @property
    def base_url(self) -> str:
        return self._base_url

    def auth_params(self) -> dict[str, str]:
        """多数服务把 Key 放在查询串里；放 Header 的子类覆写本方法即可。"""
        return {"key": self._api_key} if self._api_key else {}

    # ------------------------------------------------------------------
    # 缓存
    # ------------------------------------------------------------------
    @staticmethod
    def cache_key(path: str, params: QueryParams | None = None) -> str:
        normalized = json.dumps(params or {}, sort_keys=True, ensure_ascii=False, default=str)
        return f"{path}?{normalized}"

    def cached(self, key: str) -> Any | None:
        return self._cache.get(key)

    def remember(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def forget_all(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------
    # 请求
    # ------------------------------------------------------------------
    async def get_json(
        self,
        path: str,
        params: QueryParams | None = None,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any] | None:
        """GET 一个 JSON 接口。

        返回 `None` 表示**降级**（无 Key / 重试耗尽 / 响应不可解析），
        调用方必须据此把该数据源标记为缺失，不允许把 `None` 当业务数据用。
        """
        if not self.available:
            self.degraded = True
            logger.info("%s: 未配置 API Key，降级跳过", self.name)
            return None

        key = self.cache_key(path, params)
        if use_cache:
            hit = self.cached(key)
            if isinstance(hit, dict):
                logger.debug("%s: 缓存命中 %s", self.name, key)
                return hit

        merged = dict(params or {})
        merged.update(self.auth_params())

        attempts = self._settings.external_max_retries + 1
        for attempt in range(attempts):
            try:
                self.calls += 1
                response = await self._client.get(path, params=merged)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                logger.warning(
                    "%s: 第 %d/%d 次调用失败 %s — %s", self.name, attempt + 1, attempts, path, exc
                )
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.1 * (2**attempt))
                continue

            if not isinstance(payload, dict):
                logger.warning("%s: 响应不是 JSON 对象，放弃解析", self.name)
                break
            if use_cache:
                self.remember(key, payload)
            return payload

        self.degraded = True
        logger.warning("%s: 全部重试失败，已降级", self.name)
        return None

    async def aclose(self) -> None:
        """只关闭自己创建的 client，注入进来的由调用方负责。"""
        if self._owns_client:
            await self._client.aclose()

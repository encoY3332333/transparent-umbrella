"""历史人流量适配器（Issue #5）。

调用约束：
- 批量查询，每批最多 50 个 POI；200 个 POI 不超过 4 次网络请求。
- 未配置 Key / 请求失败时返回空 dict 并置 `degraded=True`，调用方把拥挤度标为 UNKNOWN。
- 缓存 24 小时（按 POI 集合 + 日期范围），避免重复计费。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from app.adapters.base import BaseAdapter

BATCH_SIZE = 50


def _parse_volume_payload(payload: dict[str, Any]) -> dict[int, int]:
    """兼容两种响应：

    {"data": {"205": 12000, ...}}
    {"data": [{"poiId": 205, "volume": 12000}, ...]}
    """
    raw = payload.get("data", payload)
    result: dict[int, int] = {}

    if isinstance(raw, dict):
        for key, value in raw.items():
            try:
                poi_id = int(key)
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict):
                value = value.get("volume") or value.get("historicalVolume")
            try:
                result[poi_id] = int(value)
            except (TypeError, ValueError):
                continue
        return result

    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("poiId", item.get("poi_id"))
            raw_volume = item.get("volume", item.get("historicalVolume"))
            try:
                result[int(raw_id)] = int(raw_volume)
            except (TypeError, ValueError):
                continue

    return result


class TrafficServerAdapter(BaseAdapter):
    """人流量服务代理；没有 Key 时整体降级。"""

    name = "traffic"
    cache_ttl_seconds = 24 * 60 * 60

    async def get_historical_volume(
        self,
        poi_ids: Sequence[int],
        date_range: tuple[date, date],
    ) -> dict[int, int]:
        """批量返回 `{poi_id: historical_volume}`；失败时返回空 dict。"""
        ids = sorted({int(poi_id) for poi_id in poi_ids})
        if not ids:
            return {}

        if not self.available:
            self.degraded = True
            return {}

        result: dict[int, int] = {}
        for start in range(0, len(ids), BATCH_SIZE):
            chunk = ids[start : start + BATCH_SIZE]
            params = {
                "poiIds": ",".join(str(poi_id) for poi_id in chunk),
                "startDate": date_range[0].isoformat(),
                "endDate": date_range[1].isoformat(),
            }
            payload = await self.get_json("/traffic/historical", params)
            if payload is None:
                continue
            result.update(_parse_volume_payload(payload))

        return result

"""Pydantic 模型集中出口。

按用例分文件，统一从这里导出，避免路由里出现深层 import 路径。
"""

from __future__ import annotations

from app.schemas.common import ApiResponse, PageMeta
from app.schemas.health import HealthOut
from app.schemas.itinerary import GenerateRequest, GenerateResponse, ItineraryOut

__all__ = [
    "ApiResponse",
    "GenerateRequest",
    "GenerateResponse",
    "HealthOut",
    "ItineraryOut",
    "PageMeta",
]

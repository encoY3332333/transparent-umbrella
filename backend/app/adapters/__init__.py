"""外部系统适配层。

7 个具体适配器（weather / map / traffic / event / ticket / hotel / auth）
由 Issue #5 与 #12 按需落地，本 Issue 只提供统一的 `BaseAdapter`。
"""

from __future__ import annotations

from app.adapters.base import BaseAdapter
from app.adapters.traffic import TrafficServerAdapter

__all__ = ["BaseAdapter", "TrafficServerAdapter"]

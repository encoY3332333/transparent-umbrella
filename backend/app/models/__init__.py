"""ORM 模型包。

Issue #1 只建立 `Base`；8 张业务表分别由 #5（POI / 拥挤度）、#7（行程）、
#12（后台维护）等 Issue 落地，避免骨架阶段就把数据模型写死。
"""

from __future__ import annotations

from app.models.base import Base

__all__ = ["Base"]

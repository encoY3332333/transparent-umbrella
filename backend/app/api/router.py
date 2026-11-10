"""路由汇总。

新增用例模块时只改这一个文件，`main.py` 不需要跟着动——
这样 9 个用例并行开发时不会天天冲突在同一行 import 上。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import health

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)

__all__ = ["api_router"]

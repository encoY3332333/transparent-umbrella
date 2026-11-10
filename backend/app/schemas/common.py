"""Pydantic 模型的公共基类与统一响应包装。

响应体形状严格对齐 `docs/api.md` 0.2 节：`{code, message, data}`。
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """成功响应的统一外壳。失败走 `app.core.handlers` 里的错误形状。"""

    model_config = ConfigDict(populate_by_name=True)

    code: str = "OK"
    message: str = "success"
    data: T | None = None

    @classmethod
    def ok(cls, data: T | None = None) -> ApiResponse[T]:
        return cls(data=data)


class PageMeta(BaseModel):
    """分页元信息。`page` 从 1 开始（与 docs/api.md 0.1 节一致）。"""

    page: int
    size: int
    total: int

    @property
    def pages(self) -> int:
        if self.size <= 0:
            return 0
        return (self.total + self.size - 1) // self.size

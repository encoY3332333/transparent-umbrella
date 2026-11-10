"""健康检查的响应模型。

`GET /api/health` 被 CI 冒烟测试与 `docker compose` 的 healthcheck 使用，
字段刻意保持极简：多加一个字段就多一处需要同步的契约。
"""

from __future__ import annotations

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str = "ok"
    version: str
    env: str

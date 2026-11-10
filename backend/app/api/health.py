"""健康检查接口（公开）。

CI 的冒烟测试、`docker compose` 的 healthcheck、以及上线时的探针都打这个接口，
所以它不能依赖数据库之外的外部系统——数据库自己挂了，探针要能立刻发现。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import SettingsDep
from app.schemas.health import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut, summary="健康检查")
def health(settings: SettingsDep) -> HealthOut:
    return HealthOut(status="ok", version=settings.app_version, env=settings.app_env)

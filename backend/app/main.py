"""应用入口：`uvicorn app.main:app --reload`。

启动流程刻意保持极简——建目录、配日志、挂路由。
**建表不在这里做**，交给 `alembic upgrade head`：否则开发期某次启动就会
悄悄给正式库补上缺列，迁移历史从此不可信。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__
from app.api import pages
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.handlers import register_exception_handlers
from app.core.logging import TraceIdMiddleware, configure_logging

logger = logging.getLogger(__name__)

DESCRIPTION = """
智能旅游规划系统（SmartTrip）——输入出发地、目的地、时间与预算，
结合天气、历史人流量与当地活动，自动编排可执行的行程。

- 接口契约：[docs/api.md](../docs/api.md)
- 架构说明：[docs/architecture.md](../docs/architecture.md)
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "%s 启动完成 env=%s version=%s db=%s",
        settings.app_name,
        settings.app_env,
        settings.app_version,
        settings.database_url.split("@")[-1],
    )
    yield
    logger.info("%s 已关闭", settings.app_name)


def create_app(settings: Settings | None = None) -> FastAPI:
    """应用工厂。测试里传入自定义 Settings，不必依赖真实 .env。"""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="SmartTrip 智能旅游规划",
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
    )

    # 模板与配置挂在 app.state 上：页面路由通过 request.app.state 取，便于测试替换
    app.state.settings = settings
    app.state.templates = Jinja2Templates(directory=str(settings.templates_dir))

    app.add_middleware(TraceIdMiddleware)
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

    register_exception_handlers(app)
    app.include_router(api_router)
    app.include_router(pages.router)

    return app


app = create_app()

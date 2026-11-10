"""数据库引擎与会话工厂。

只做一件事：把 `DATABASE_URL` 翻译成一个配置正确的 `Engine`。
开发/测试/演示三套环境的差异**只在这一个变量**（见 docs/architecture.md 第 7 节）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings


def build_engine(settings: Settings) -> Engine:
    """按 URL 前缀决定连接参数，调用方不需要关心用的是 SQLite 还是 MySQL。"""
    url = settings.database_url
    options: dict[str, Any] = {"pool_pre_ping": True}

    if url.startswith("sqlite"):
        # SQLite 默认禁止跨线程复用连接，FastAPI 的线程池会踩到这一点
        options["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            # 内存库每个连接都是独立的库，必须用 StaticPool 共享同一条连接，
            # 否则 alembic 建的表在测试里查不到（Issue #1 技术备注）
            options["poolclass"] = StaticPool
    else:
        options["pool_size"] = settings.db_pool_size
        options["pool_recycle"] = settings.db_pool_recycle_seconds

    return create_engine(url, **options)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """`expire_on_commit=False`：service 提交后仍能读对象属性，避免 DetachedInstanceError。"""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def resolve_database_url(settings: Settings) -> str:
    """Alembic 与运行时共用同一个解析结果，防止两边连到不同的库。"""
    return settings.database_url

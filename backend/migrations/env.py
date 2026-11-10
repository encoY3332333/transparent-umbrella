"""Alembic 运行环境。

两个约定：
1. 连接串只从 `Settings` 读，不从 alembic.ini 读——否则改库要改两个地方；
2. 复用 `app.core.db.build_engine`——否则 SQLite 内存库会因连不上 StaticPool
   而在测试里建表失败。
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.engine import Connection

# 允许 `alembic` 命令从 backend/ 之外调用时也能 import 到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.db import build_engine  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None and config.get_section("loggers"):
    fileConfig(config.config_file_name)

settings = get_settings()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """仅生成 SQL（`alembic upgrade head --sql`），不连库。"""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = build_engine(settings)
    with engine.connect() as connection:
        _migrate(connection)
    engine.dispose()


def _migrate(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=settings.database_url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

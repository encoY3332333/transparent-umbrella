"""依赖注入：路由只声明「我需要什么」，不自己造资源。

`get_engine` / `get_session_factory` 都做了缓存——每个请求都新建引擎会把连接池打爆。
测试里要换库，先 `get_engine.cache_clear()` 再改环境变量。
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import build_engine, build_session_factory


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return build_engine(get_settings())


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return build_session_factory(get_engine())


def get_db() -> Iterator[Session]:
    """请求级会话。

    这里**不开事务**——事务边界归 service 层（architecture.md 分层约束第 2 条），
    路由只借用会话做查询。
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_engine_cache() -> None:
    """测试与运维用：清掉引擎缓存，下次取依赖时按当前配置重建。"""
    get_session_factory.cache_clear()
    get_engine.cache_clear()


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[Session, Depends(get_db)]

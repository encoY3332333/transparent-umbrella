"""依赖注入：路由只声明「我需要什么」，不自己造资源。

`get_engine` / `get_session_factory` 都做了缓存——每个请求都新建引擎会把连接池打爆。
测试里要换库，先 `get_engine.cache_clear()` 再改环境变量。
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import build_engine, build_session_factory
from app.core.errors import BusinessError, ErrorCode
from app.core.security import ACCESS_TOKEN_COOKIE, TokenError, tourist_id_from_token
from app.models.tourist import Tourist


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


def get_optional_tourist(request: Request, session: DbDep) -> Tourist | None:
    """解析当前登录游客，未登录或 token 无效都返回 None。

    token 优先取 HttpOnly Cookie（浏览器路径），其次取 `Authorization: Bearer`
    （脚本 / 自动化测试路径）——两条路径都支持，测试就不必为发 Cookie 折腾
    半天，线上也不必为了兼容脚本牺牲 Cookie 的安全性。
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        authorization = request.headers.get("authorization", "")
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() == "bearer" and credentials:
            token = credentials.strip()
    if not token:
        return None
    try:
        tourist_id = tourist_id_from_token(token, get_settings())
    except TokenError:
        # 过期 / 伪造的 token 一律当未登录：前端拿到 None 就重新走登录，
        # 比抛 401 更适合「游客本来就可以什么都不登录」的产品设定（BR-03）。
        return None
    return session.get(Tourist, tourist_id)


OptionalTouristDep = Annotated[Tourist | None, Depends(get_optional_tourist)]


def get_current_tourist(tourist: OptionalTouristDep) -> Tourist:
    """要求必须登录的依赖。未登录抛 UNAUTHORIZED（401 + AUTH 域错误码）。"""
    if tourist is None:
        raise BusinessError(ErrorCode.UNAUTHORIZED)
    return tourist


CurrentTouristDep = Annotated[Tourist, Depends(get_current_tourist)]

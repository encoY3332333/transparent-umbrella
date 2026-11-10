"""数据库层：引擎参数与请求级会话。"""

from __future__ import annotations

from sqlalchemy import text

from app.core.config import Settings
from app.core.db import build_engine, build_session_factory, resolve_database_url
from app.core.deps import get_db


def test_memory_sqlite_uses_static_pool() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    engine = build_engine(settings)

    assert engine.pool.__class__.__name__ == "StaticPool"
    # 内存库必须跨连接共享，否则 A 连接建的表 B 连接看不到
    with engine.connect() as first, engine.connect() as second:
        first.execute(text("create table t (id integer primary key)"))
        first.commit()
        assert second.execute(text("select count(*) from t")).scalar_one() == 0

    engine.dispose()


def test_file_sqlite_keeps_check_same_thread_off(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(database_url=f"sqlite+pysqlite:///{tmp_path / 'unit.db'}")
    engine = build_engine(settings)

    assert engine.pool.__class__.__name__ != "StaticPool"
    engine.dispose()


def test_session_factory_does_not_expire_on_commit() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")
    factory = build_session_factory(build_engine(settings))

    assert factory.kw["expire_on_commit"] is False
    assert factory.kw["autoflush"] is False


def test_resolve_database_url_is_single_source() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")

    assert resolve_database_url(settings) == "sqlite+pysqlite:///:memory:"


def test_get_db_yields_usable_session() -> None:
    sessions = get_db()
    session = next(sessions)

    try:
        assert session.execute(text("select 1")).scalar_one() == 1
    finally:
        sessions.close()

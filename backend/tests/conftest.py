"""测试夹具。

三条纪律：
1. 每个测试都跑在内存 SQLite 上，绝不碰本地 `smarttrip.db`；
2. 环境变量先设好再构造 `Settings`，否则 `.env` 会渗进断言；
3. `TestClient` 必须用 `with` 启动，否则 lifespan 不执行，`app.state` 里少东西。

另外每个测试都要清掉进程级缓存（引擎、策略参数）：它们按 `DATABASE_URL` 之外
的状态缓存，跨用例复用会让「这条数据是谁插的」变得不可解释。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.deps import reset_engine_cache
from app.main import create_app
from app.services.strategy_service import reset_strategy_cache


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    get_settings.cache_clear()
    reset_engine_cache()
    reset_strategy_cache()
    yield
    get_settings.cache_clear()
    reset_engine_cache()
    reset_strategy_cache()


@pytest.fixture
def settings(isolated_env: None) -> Settings:
    return get_settings()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    # raise_server_exceptions=False：这样才能断言 500 的统一错误响应体
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

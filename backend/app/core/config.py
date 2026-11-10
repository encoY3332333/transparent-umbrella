"""应用配置：唯一的环境变量入口。

约定（Issue #1 验收标准）：`.env.example` 里的每一项在 `Settings` 中都有同名字段，
不多不少。新增配置项时必须同步改 `.env.example`，否则 Code Review 打回。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """从环境变量 / `backend/.env` 读取的运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------- 应用 ----------------------------
    app_name: str = "smart-trip"
    app_env: Literal["dev", "test", "ci", "prod"] = "dev"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_version: str = "0.1.0"
    secret_key: str = "change_me_in_local_env"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ---------------------------- 数据库 --------------------------
    database_url: str = "sqlite+pysqlite:///./smarttrip.db"
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60)

    # ---------------------------- 认证 ----------------------------
    jwt_secret: str = "change_me_in_local_env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=1440, ge=1)
    login_max_attempts: int = Field(default=5, ge=1, le=20)
    login_lock_minutes: int = Field(default=5, ge=1, le=120)

    # ---------------------------- 缓存 ----------------------------
    cache_ttl_seconds: int = Field(default=3600, ge=0, le=86400)
    strategy_cache_ttl_seconds: int = Field(default=60, ge=0, le=3600)

    # ---------------------------- 第三方服务 ----------------------
    weather_base_url: str = "https://api.openweathermap.org/data/3.0"
    weather_api_key: str = ""
    map_base_url: str = "https://restapi.amap.com/v3"
    map_api_key: str = ""
    traffic_base_url: str = "https://traffic.example.edu/api"
    traffic_api_key: str = ""
    transit_base_url: str = "https://transit.example.edu/api"
    transit_api_key: str = ""
    event_base_url: str = "https://event.example.edu/api"
    event_api_key: str = ""
    hotel_base_url: str = "https://hotel.example.edu/api"
    hotel_api_key: str = ""
    auth_base_url: str = "https://auth.example.edu/api"
    auth_client_id: str = ""
    auth_client_secret: str = ""

    # ---------------------------- 外部调用约束 --------------------
    plan_external_call_limit: int = Field(default=60, ge=1, le=500)
    external_connect_timeout: float = Field(default=1.5, gt=0)
    external_read_timeout: float = Field(default=3.0, gt=0)
    external_max_retries: int = Field(default=2, ge=0, le=5)

    # ---------------------------- 排程引擎 ------------------------
    strategy_w_pref: float = Field(default=0.10, ge=0, le=1)
    strategy_w_weather: float = Field(default=0.25, ge=0, le=1)
    strategy_w_crowd: float = Field(default=0.23, ge=0, le=1)
    strategy_w_travel: float = Field(default=0.14, ge=0, le=1)
    strategy_w_cost: float = Field(default=0.28, ge=0, le=1)
    strategy_max_iteration: int = Field(default=30, ge=1, le=500)
    strategy_daily_hours: int = Field(default=10, ge=1, le=24)

    # ---------------------------- 管理后台 ------------------------
    admin_init_username: str = "admin"
    admin_init_password: str = "change_me_in_local_env"

    # ---------------------------- 分享服务 ------------------------
    share_link_ttl_days: int = Field(default=7, ge=1, le=30)
    share_sign_salt: str = "change_me_in_local_env"

    @model_validator(mode="after")
    def _check_strategy_weights(self) -> Settings:
        """BR-23：五项权重之和必须为 1（误差 < 0.001）。"""
        total = (
            self.strategy_w_pref
            + self.strategy_w_weather
            + self.strategy_w_crowd
            + self.strategy_w_travel
            + self.strategy_w_cost
        )
        if abs(total - 1.0) > 0.001:
            msg = f"STRATEGY_W_* 五项权重之和必须为 1，当前为 {total:.4f}"
            raise ValueError(msg)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def strategy_weights(self) -> dict[str, float]:
        """与 `/api/admin/strategies/current` 的 `weights` 字段同名同序。"""
        return {
            "preference": self.strategy_w_pref,
            "weather": self.strategy_w_weather,
            "crowd": self.strategy_w_crowd,
            "travel": self.strategy_w_travel,
            "cost": self.strategy_w_cost,
        }

    @property
    def templates_dir(self) -> Path:
        return BACKEND_DIR / "app" / "templates"

    @property
    def static_dir(self) -> Path:
        return BACKEND_DIR / "app" / "static"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """进程内单例。测试里改完环境变量要调用 `get_settings.cache_clear()`。"""
    return Settings()

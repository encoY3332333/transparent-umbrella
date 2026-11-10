"""配置校验：BR-23（权重和=1）与 .env.example 字段对齐。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import BACKEND_DIR, Settings

ENV_EXAMPLE = BACKEND_DIR.parent / ".env.example"


def test_defaults_are_valid(settings: Settings) -> None:
    assert settings.app_env == "test"
    assert settings.is_production is False
    assert sum(settings.strategy_weights.values()) == pytest.approx(1.0)


def test_strategy_weights_keys_match_api_contract(settings: Settings) -> None:
    assert list(settings.strategy_weights) == ["preference", "weather", "crowd", "travel", "cost"]


def test_strategy_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            strategy_w_pref=0.5,
            strategy_w_weather=0.5,
            strategy_w_crowd=0.5,
            strategy_w_travel=0.1,
            strategy_w_cost=0.1,
        )

    assert "权重之和必须为 1" in str(excinfo.value)


def test_production_flag() -> None:
    assert Settings(app_env="prod").is_production is True


def test_every_env_example_key_exists_on_settings() -> None:
    """验收标准：`.env.example` 里有的都能读到，读到的都在 `.env.example` 里。"""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    env_keys = {
        match.group(1).lower()
        for match in re.finditer(r"^([A-Z][A-Z0-9_]*)=", text, flags=re.MULTILINE)
    }
    assert env_keys, "未从 .env.example 解析到任何配置项"

    settings_keys = set(Settings.model_fields)
    missing_on_settings = env_keys - settings_keys
    assert not missing_on_settings, (
        f".env.example 中这些键在 Settings 里没有字段: {missing_on_settings}"
    )

    # APP_VERSION / APP_NAME 等可由代码给出默认值，允许只在 Settings 中存在
    only_in_settings = settings_keys - env_keys
    assert only_in_settings <= {"app_version"}, (
        f"Settings 存在未在 .env.example 声明的字段: {only_in_settings}"
    )


def test_templates_and_static_dirs_exist(settings: Settings) -> None:
    assert settings.templates_dir.is_dir()
    assert (settings.templates_dir / "base.html").is_file()
    assert settings.static_dir.is_dir()
    assert Path(settings.static_dir, "vendor", "htmx.min.js").is_file()

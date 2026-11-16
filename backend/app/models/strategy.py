"""推荐策略参数模型（Issue #13 / UC-09）。

**一张表同时承担「当前生效」与「历史版本」**：最新版本即当前生效，
不另设 `current_version` 指针——指针和数据两张表不同步，是这类配置最经典的 bug 来源，
而「按版本倒序取第一条」这个查询在 SQLite / MySQL 上都是一次索引扫描。

表是 append-only：不做 `UPDATE`，改参数就是插一条新版本（BR-24 历史版本永久保留）。
回滚同样插新版本（`note` 里记明来源版本），所以「回滚过」这件事在版本列表里是可见的，
而不是把指针拨回去、看起来什么都没发生过。

五项权重存成 5 个独立列而不是 JSON：它们是唯一需要参与校验、比较与展示的字段，
拆成列后 `SELECT` 出来就能直接断言；节假日系数、阈值这些结构不固定的才进 JSON。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# 与 `docs/api.md` 10.1 的 `weights` 字段同名同序。五处（模型 / 校验 / 页面 /
# engine 适配 / 测试）都从这一个元组取，避免有人写 `w_crowd`、有人写 `crowd`。
WEIGHT_KEYS: tuple[str, ...] = ("preference", "weather", "crowd", "travel", "cost")

# engine 的 `Weights` 用缩写名 `pref`，API 契约用 `preference`。
# 映射只有这一个方向、一张表，放在模型旁边最容易核对。
ENGINE_WEIGHT_NAMES: dict[str, str] = {
    "preference": "pref",
    "weather": "weather",
    "crowd": "crowd",
    "travel": "travel",
    "cost": "cost",
}


def _utcnow() -> datetime:
    """带时区的 UTC 时间。与 `models/itinerary.py` 同一种写法，避免 naive 时间入库。"""
    return datetime.now(UTC)


class StrategyParameter(Base):
    """一条策略参数版本。`version` 从 1 开始自增，永不复用。"""

    __tablename__ = "strategy_parameter"
    __table_args__ = (
        # 版本号唯一：并发发布时靠它把冲突挡在数据库层，而不是事后去重
        UniqueConstraint("version", name="uq_strategy_parameter_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    w_pref: Mapped[float] = mapped_column(Float, nullable=False)
    w_weather: Mapped[float] = mapped_column(Float, nullable=False)
    w_crowd: Mapped[float] = mapped_column(Float, nullable=False)
    w_travel: Mapped[float] = mapped_column(Float, nullable=False)
    w_cost: Mapped[float] = mapped_column(Float, nullable=False)

    # 节假日人流系数，形如 {"春节": 2.2, "工作日": 1.0}；键是运营自定义的中文名
    holiday_factors_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # 规则阈值（单日时长、步行上限、长途阈值、拥挤避峰线、迭代次数）
    thresholds_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # 被关闭的兜底规则，形如 ["crowd"]；与「该维度权重为 0」组合时需要二次确认
    disabled_fallbacks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # 变更说明 / 回滚来源，例如 "回滚自 v3"
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="admin")
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<StrategyParameter v{self.version} by={self.created_by!r}>"


__all__ = ["ENGINE_WEIGHT_NAMES", "WEIGHT_KEYS", "StrategyParameter"]

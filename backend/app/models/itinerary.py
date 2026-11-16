"""行程相关 ORM 模型（Issue #4）。

三张表：`itinerary` / `itinerary_day` / `itinerary_activity`。
表名统一带 `itinerary_` 前缀（第一张本身就叫 `itinerary`），因为 MySQL 8 上
`activities` 这种通用名在多人并行开发时很容易和别的模块撞名。

`status` 只在本 Issue 写入 `PROPOSED`；`ADJUSTED` / `CONFIRMED` 由 UC-05（#9）推进。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _utcnow() -> datetime:
    """带时区的 UTC 时间。

    用 `datetime.utcnow()` 会得到 naive 时间，写进 MySQL 再读出来时区信息就丢了，
    跨时区展示会差 8 小时。统一用带 tz 的版本。
    """
    return datetime.now(UTC)


class ItineraryStatus:
    """行程状态常量。

    不用 `enum.Enum` 是为了让 Alembic 迁移不产生 MySQL ENUM 类型——
    ENUM 加值要 ALTER TABLE，而状态机在后续 Issue 里还会变。
    """

    PROPOSED = "PROPOSED"
    ADJUSTED = "ADJUSTED"
    CONFIRMED = "CONFIRMED"

    ALL = (PROPOSED, ADJUSTED, CONFIRMED)


class Itinerary(Base):
    """一套候选方案。一次生成请求可以产出 1–3 条，`batch_id` 把它们串起来。"""

    __tablename__ = "itinerary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 同一次生成请求产出的多套方案共享 batch_id，前端「换一套看看」靠它查同批
    batch_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=ItineraryStatus.PROPOSED, nullable=False, index=True
    )

    city: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # 预算相关用 Float：金额在课程项目里不做小数精度要求，
    # 真要记钱的地方（后台结算）才需要 Decimal，这里用不上。
    budget: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 推荐理由存 JSON 文本：理由条数不固定，拆表收益不大，
    # 而且前端只整块展示，不做查询条件。
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    degraded_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    day_plans: Mapped[list[ItineraryDay]] = relationship(
        back_populates="itinerary",
        cascade="all, delete-orphan",
        order_by="ItineraryDay.day_index",
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Itinerary id={self.id} title={self.title!r} status={self.status}>"


class ItineraryDay(Base):
    """一天的容器。`day_index` 从 0 开始，和 engine 里的 `day_index` 对齐。"""

    __tablename__ = "itinerary_day"
    __table_args__ = (
        # 同一条行程里 day_index 不能重复，否则前端按天渲染会错位
        UniqueConstraint("itinerary_id", "day_index", name="uq_itinerary_day_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    itinerary_id: Mapped[int] = mapped_column(
        ForeignKey("itinerary.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    day_date: Mapped[date] = mapped_column(Date, nullable=False)

    itinerary: Mapped[Itinerary] = relationship(back_populates="day_plans")
    activities: Mapped[list[Activity]] = relationship(
        back_populates="day",
        cascade="all, delete-orphan",
        order_by="Activity.start_minute",
    )


class Activity(Base):
    """一个活动。

    **时间存「当日分钟数」而不是 `Time`**：排程算法全程在分钟维度做加减
    （见 `engine/packer.py`），存成 `Time` 每次读出来都要再转一次，
    而且跨零点的活动（夜游 23:00–01:00）用 `Time` 表示会丢信息。
    API 出参时再转成 `HH:MM`。
    """

    __tablename__ = "itinerary_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day_id: Mapped[int] = mapped_column(
        ForeignKey("itinerary_day.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # poi_id 不设外键：POI 由 #5 的 seed 维护，允许行程引用了已下架的 POI
    # （下架后行程仍要能看，只是不能再调整到它）。用 #9 校验时再查状态。
    poi_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    poi_name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")

    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)

    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    travel_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    crowd_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    crowd_shifted: Mapped[bool] = mapped_column(default=False, nullable=False)
    long_transfer: Mapped[bool] = mapped_column(default=False, nullable=False)
    # UC-05「锁定必去项」用；本 Issue 建表时就带上，免得后面再加迁移
    locked: Mapped[bool] = mapped_column(default=False, nullable=False)

    day: Mapped[ItineraryDay] = relationship(back_populates="activities")


__all__ = [
    "Activity",
    "Itinerary",
    "ItineraryDay",
    "ItineraryStatus",
]

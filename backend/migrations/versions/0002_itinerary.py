"""行程三表：itinerary / itinerary_day / itinerary_activity（Issue #4）

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12 22:20:00

手写而非 autogenerate：`render_as_batch` 在 SQLite 上生成的迁移是
「建临时表 → 拷数据 → 删旧表 → 改名」，可读性极差；这里表是全新的，
直接 `create_table` 在两个方言上都对。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "itinerary",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # 同一次生成请求产出的多套方案共享 batch_id
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("budget", sa.Float(), nullable=False),
        sa.Column("total_cost", sa.Float(), nullable=False),
        sa.Column("total_minutes", sa.Integer(), nullable=False),
        sa.Column("reasons_json", sa.Text(), nullable=False),
        sa.Column("degraded_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_itinerary")),
    )
    op.create_index(op.f("ix_itinerary_batch_id"), "itinerary", ["batch_id"], unique=False)
    op.create_index(op.f("ix_itinerary_status"), "itinerary", ["status"], unique=False)

    op.create_table(
        "itinerary_day",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("itinerary_id", sa.Integer(), nullable=False),
        sa.Column("day_index", sa.Integer(), nullable=False),
        sa.Column("day_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["itinerary_id"],
            ["itinerary.id"],
            name=op.f("fk_itinerary_day_itinerary_id_itinerary"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_itinerary_day")),
        # 同一条行程里 day_index 不能重复
        sa.UniqueConstraint(
            "itinerary_id", "day_index", name="uq_itinerary_day_index"
        ),
    )
    op.create_index(
        op.f("ix_itinerary_day_itinerary_id"), "itinerary_day", ["itinerary_id"], unique=False
    )

    op.create_table(
        "itinerary_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("day_id", sa.Integer(), nullable=False),
        # 不设外键：POI 由 #5 维护，允许行程引用已下架的景点
        sa.Column("poi_id", sa.Integer(), nullable=False),
        sa.Column("poi_name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("travel_minutes", sa.Integer(), nullable=False),
        sa.Column("crowd_index", sa.Integer(), nullable=True),
        sa.Column("crowd_shifted", sa.Boolean(), nullable=False),
        sa.Column("long_transfer", sa.Boolean(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["day_id"],
            ["itinerary_day.id"],
            name=op.f("fk_itinerary_activity_day_id_itinerary_day"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_itinerary_activity")),
    )
    op.create_index(
        op.f("ix_itinerary_activity_day_id"), "itinerary_activity", ["day_id"], unique=False
    )
    op.create_index(
        op.f("ix_itinerary_activity_poi_id"), "itinerary_activity", ["poi_id"], unique=False
    )


def downgrade() -> None:
    # 先删子表再删父表：MySQL 上外键会挡住删父表
    op.drop_index(op.f("ix_itinerary_activity_poi_id"), table_name="itinerary_activity")
    op.drop_index(op.f("ix_itinerary_activity_day_id"), table_name="itinerary_activity")
    op.drop_table("itinerary_activity")

    op.drop_index(op.f("ix_itinerary_day_itinerary_id"), table_name="itinerary_day")
    op.drop_table("itinerary_day")

    op.drop_index(op.f("ix_itinerary_status"), table_name="itinerary")
    op.drop_index(op.f("ix_itinerary_batch_id"), table_name="itinerary")
    op.drop_table("itinerary")

"""策略参数版本表（Issue #13 / UC-09）

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-16 22:40:00

手写迁移的理由与 0002 相同：表是全新的，`create_table` 比 autogenerate 在
SQLite 上生成的「建临时表 → 拷数据 → 改名」可读得多，两个方言也对。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_parameter",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("w_pref", sa.Float(), nullable=False),
        sa.Column("w_weather", sa.Float(), nullable=False),
        sa.Column("w_crowd", sa.Float(), nullable=False),
        sa.Column("w_travel", sa.Float(), nullable=False),
        sa.Column("w_cost", sa.Float(), nullable=False),
        sa.Column("holiday_factors_json", sa.Text(), nullable=False),
        sa.Column("thresholds_json", sa.Text(), nullable=False),
        sa.Column("disabled_fallbacks_json", sa.Text(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_strategy_parameter")),
        # 版本号唯一：并发发布时由数据库挡住重复版本
        sa.UniqueConstraint("version", name="uq_strategy_parameter_version"),
    )
    op.create_index(
        op.f("ix_strategy_parameter_version"), "strategy_parameter", ["version"], unique=False
    )


def downgrade() -> None:
    # 历史版本按 BR-24 不可删——但迁移回滚是「撤掉这张表」，不是业务删除
    op.drop_index(op.f("ix_strategy_parameter_version"), table_name="strategy_parameter")
    op.drop_table("strategy_parameter")

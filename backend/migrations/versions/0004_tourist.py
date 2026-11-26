"""游客账号表 + 行程归属列（Issue #2 / UC-01）

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-26 10:00:00

两张改动：
1. 新建 `tourist` 表（手机号唯一、偏好标签 JSON、登录时间）。
2. 给 `itinerary` 加可空的 `tourist_id`。

**为什么 `tourist_id` 必须可空**：BR-03 明确「未登录可以生成行程，但不能保存」。
未登录时生成的行程仍然要落库（用户能看、能调整、能分享），只是不属于任何人；
一旦改成 NOT NULL，就必须给「匿名行程」编一个假账号，反而更难治理。

手写迁移而不是 autogenerate：SQLite 上 autogenerate 处理「加外键列」会生成
建临时表拷数据的脚本，可读性差且对 MySQL 8 行为不同；这里只是两张表的小改动，
手写两个方言都对。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tourist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("nickname", sa.String(length=40), nullable=False),
        sa.Column("preference_tags_json", sa.Text(), nullable=False),
        sa.Column("party_type", sa.String(length=16), nullable=False),
        sa.Column("pace", sa.String(length=16), nullable=False),
        sa.Column("budget_level", sa.String(length=16), nullable=False),
        sa.Column("preference_saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone", name="uq_tourist_phone"),
    )
    # 手机号查询是登录热路径，唯一约束在 MySQL 上会隐式建索引，SQLite 同理；
    # 显式再建一个命名索引只为让 `EXPLAIN` 输出可读。
    op.create_index("ix_tourist_phone", "tourist", ["phone"], unique=True)

    # 加列与加外键都放进 batch：SQLite 不支持 ALTER 约束，batch 模式会走
    # 「建临时表 → 拷数据 → 改名」，MySQL 8 上 batch 退化成普通 ALTER，两边都对。
    with op.batch_alter_table("itinerary") as batch:
        batch.add_column(sa.Column("tourist_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_itinerary_tourist_id",
            "tourist",
            ["tourist_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_itinerary_tourist_id", ["tourist_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("itinerary") as batch:
        batch.drop_index("ix_itinerary_tourist_id")
        batch.drop_constraint("fk_itinerary_tourist_id", type_="foreignkey")
        batch.drop_column("tourist_id")
    op.drop_index("ix_tourist_phone", table_name="tourist")
    op.drop_table("tourist")

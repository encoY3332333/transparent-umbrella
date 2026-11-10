"""基线迁移：只建立迁移版本表，不建业务表

Revision ID: 0001
Revises:
Create Date: 2026-11-10 20:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """业务表随功能 Issue 逐个落地：

    - #5 → poi / crowd_index
    - #7 → itinerary / itinerary_day / activity
    - #2 → tourist / preference
    - #12 → strategy_parameter / feedback

    现在留空，是为了让 `alembic upgrade head` 从第一天起就能跑通并且幂等——
    骨架阶段先证明「迁移链路可用」，比先塞一堆没有对应代码的表更有价值。
    """


def downgrade() -> None:
    """基线不持有任何 schema，无需回滚动作。"""

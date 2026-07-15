"""增加面试风格维度。

Revision ID: 20260713_0009
Revises: 20260713_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_0009"
down_revision: str | None = "20260713_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_levels(table: str) -> None:
    for name, default in (
        ("pressure_level", "3"),
        ("depth_level", "4"),
        ("guidance_level", "2"),
    ):
        op.add_column(
            table,
            sa.Column(name, sa.Integer(), nullable=False, server_default=default),
        )
        op.create_check_constraint(f"ck_{table}_{name}", table, f"{name} BETWEEN 1 AND 5")
        op.alter_column(table, name, server_default=None)


def upgrade() -> None:
    _add_levels("training_drafts")
    _add_levels("interview_sessions")


def downgrade() -> None:
    for table in ("interview_sessions", "training_drafts"):
        for name in ("guidance_level", "depth_level", "pressure_level"):
            op.drop_constraint(f"ck_{table}_{name}", table, type_="check")
            op.drop_column(table, name)

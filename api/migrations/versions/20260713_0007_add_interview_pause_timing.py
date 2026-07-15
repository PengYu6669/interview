"""增加面试暂停计时。

Revision ID: 20260713_0007
Revises: 20260713_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_0007"
down_revision: str | None = "20260713_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column(
            "accumulated_pause_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column("interview_sessions", "accumulated_pause_seconds", server_default=None)


def downgrade() -> None:
    op.drop_column("interview_sessions", "accumulated_pause_seconds")
    op.drop_column("interview_sessions", "paused_at")

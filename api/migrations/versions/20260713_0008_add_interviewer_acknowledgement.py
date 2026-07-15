"""增加面试承接语。

Revision ID: 20260713_0008
Revises: 20260713_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_0008"
down_revision: str | None = "20260713_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_turns",
        sa.Column(
            "transition",
            sa.String(length=120),
            nullable=False,
            server_default="好的，我了解了。我们继续。",
        ),
    )
    op.alter_column("interview_turns", "transition", server_default=None)


def downgrade() -> None:
    op.drop_column("interview_turns", "transition")

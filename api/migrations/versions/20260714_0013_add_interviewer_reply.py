"""增加面试官长回复。

Revision ID: 20260714_0013
Revises: 20260714_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_0013"
down_revision: str | None = "20260714_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_turns",
        sa.Column("interviewer_reply", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interview_turns", "interviewer_reply")

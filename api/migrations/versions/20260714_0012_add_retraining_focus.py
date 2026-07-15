"""增加复训重点。

Revision ID: 20260714_0012
Revises: 20260714_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_0012"
down_revision: str | None = "20260714_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("training_drafts", "interview_sessions"):
        op.add_column(
            table,
            sa.Column(
                "training_focus",
                sa.String(length=500),
                nullable=False,
                server_default="",
            ),
        )
        op.alter_column(table, "training_focus", server_default=None)


def downgrade() -> None:
    op.drop_column("interview_sessions", "training_focus")
    op.drop_column("training_drafts", "training_focus")

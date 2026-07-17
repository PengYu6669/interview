"""add retraining source

Revision ID: 20260716_0029
Revises: 20260716_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0029"
down_revision: str | None = "20260716_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("training_drafts", "interview_sessions"):
        op.add_column(
            table,
            sa.Column("source_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_source_session_id",
            table,
            "interview_sessions",
            ["source_session_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{table}_source_session_id", table, ["source_session_id"])


def downgrade() -> None:
    for table in ("interview_sessions", "training_drafts"):
        op.drop_index(f"ix_{table}_source_session_id", table_name=table)
        op.drop_constraint(
            f"fk_{table}_source_session_id", table, type_="foreignkey"
        )
        op.drop_column(table, "source_session_id")

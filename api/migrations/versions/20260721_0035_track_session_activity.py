"""track session activity for admin metrics

Revision ID: 20260721_0035
Revises: 20260720_0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0035"
down_revision: str | None = "20260720_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auth_sessions",
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE auth_sessions SET last_active_at = created_at")
    op.alter_column("auth_sessions", "last_active_at", nullable=False)
    op.create_index("ix_auth_sessions_last_active_at", "auth_sessions", ["last_active_at"])


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_last_active_at", table_name="auth_sessions")
    op.drop_column("auth_sessions", "last_active_at")

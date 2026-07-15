"""Add interview report claim verification fields.

Revision ID: 20260715_0020
Revises: 20260715_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0020"
down_revision: str | None = "20260715_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_reports",
        sa.Column(
            "verification_status",
            sa.String(20),
            server_default="not_run",
            nullable=False,
        ),
    )
    op.add_column(
        "interview_reports",
        sa.Column("verification_error", sa.String(500), nullable=True),
    )
    op.add_column(
        "interview_reports",
        sa.Column(
            "verified_claims",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("interview_reports", "verified_claims")
    op.drop_column("interview_reports", "verification_error")
    op.drop_column("interview_reports", "verification_status")

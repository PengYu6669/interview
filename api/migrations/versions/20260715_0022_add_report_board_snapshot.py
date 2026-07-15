"""Store the latest system design board snapshot with reports."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260715_0022"
down_revision = "20260715_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_reports",
        sa.Column("board_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interview_reports", "board_snapshot")

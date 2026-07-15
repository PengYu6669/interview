"""Add spaced review scheduling fields to question progress."""

import sqlalchemy as sa
from alembic import op

revision = "20260715_0023"
down_revision = "20260715_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_question_progress",
        sa.Column("review_interval_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_question_progress",
        sa.Column("review_streak", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "user_question_progress",
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "user_question_progress",
        sa.Column("review_due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_user_question_progress_review_due_at", "user_question_progress", ["review_due_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_user_question_progress_review_due_at", table_name="user_question_progress")
    op.drop_column("user_question_progress", "review_due_at")
    op.drop_column("user_question_progress", "last_reviewed_at")
    op.drop_column("user_question_progress", "review_streak")
    op.drop_column("user_question_progress", "review_interval_days")

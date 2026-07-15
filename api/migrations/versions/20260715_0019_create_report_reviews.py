"""Create interview report review records.

Revision ID: 20260715_0019
Revises: 20260714_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0019"
down_revision: str | None = "20260714_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_report_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skill_index", sa.Integer(), nullable=False),
        sa.Column("skill", sa.String(80), nullable=False),
        sa.Column("original_score", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("decision", sa.String(20), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("revised_score", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("skill_index >= 0", name="ck_interview_report_reviews_skill_index"),
        sa.CheckConstraint(
            "original_score >= 0 AND original_score <= 100",
            name="ck_interview_report_reviews_original_score",
        ),
        sa.CheckConstraint(
            "revised_score IS NULL OR (revised_score >= 0 AND revised_score <= 100)",
            name="ck_interview_report_reviews_revised_score",
        ),
        sa.ForeignKeyConstraint(["report_id"], ["interview_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "client_request_id",
            name="uq_interview_report_reviews_user_request",
        ),
    )
    op.create_index(
        "ix_interview_report_reviews_report_id", "interview_report_reviews", ["report_id"]
    )
    op.create_index(
        "ix_interview_report_reviews_session_id", "interview_report_reviews", ["session_id"]
    )
    op.create_index("ix_interview_report_reviews_user_id", "interview_report_reviews", ["user_id"])
    op.create_index("ix_interview_report_reviews_status", "interview_report_reviews", ["status"])


def downgrade() -> None:
    op.drop_table("interview_report_reviews")

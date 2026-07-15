"""增加报告生成状态。

Revision ID: 20260714_0015
Revises: 20260714_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0015"
down_revision: str | None = "20260714_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column(
            "report_status",
            sa.String(length=20),
            nullable=False,
            server_default="not_started",
        ),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("report_error", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("report_generation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("report_generation_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "interview_sessions",
        sa.Column("report_generation_finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_interview_sessions_report_status",
        "interview_sessions",
        "report_status IN ('not_started', 'generating', 'ready', 'failed')",
    )
    op.create_index(
        "ix_interview_sessions_report_status",
        "interview_sessions",
        ["report_status"],
    )
    op.execute(
        """
        UPDATE interview_sessions AS session
        SET report_status = 'ready',
            report_generation_finished_at = report.created_at
        FROM interview_reports AS report
        WHERE report.session_id = session.id
        """
    )
    op.alter_column("interview_sessions", "report_status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_interview_sessions_report_status", table_name="interview_sessions")
    op.drop_constraint(
        "ck_interview_sessions_report_status",
        "interview_sessions",
        type_="check",
    )
    for column in (
        "report_generation_finished_at",
        "report_generation_started_at",
        "report_generation_id",
        "report_error",
        "report_status",
    ):
        op.drop_column("interview_sessions", column)

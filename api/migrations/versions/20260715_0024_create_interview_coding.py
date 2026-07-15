"""create interview coding workspaces and runs

Revision ID: 20260715_0024
Revises: 20260715_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0024"
down_revision: str | None = "20260715_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORIGINAL_INTERVIEW_TYPES = (
    "'comprehensive', 'project', 'technical', 'system_design', 'behavioral', 'weak_area'"
)
CODING_INTERVIEW_TYPES = (
    "'comprehensive', 'project', 'technical', 'system_design', 'coding', "
    "'behavioral', 'weak_area'"
)


def upgrade() -> None:
    for table in ("training_drafts", "interview_sessions"):
        op.drop_constraint(f"ck_{table}_interview_type", table, type_="check")
        op.create_check_constraint(
            f"ck_{table}_interview_type",
            table,
            f"interview_type IN ({CODING_INTERVIEW_TYPES})",
        )
    op.add_column(
        "interview_reports",
        sa.Column(
            "coding_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_table(
        "interview_coding_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phase_index", sa.Integer(), nullable=False),
        sa.Column("question_index", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("client_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("complexity_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "phase_index", "question_index", "revision"),
        sa.UniqueConstraint("user_id", "client_snapshot_id"),
    )
    op.create_index(
        "ix_interview_coding_snapshots_session_id",
        "interview_coding_snapshots",
        ["session_id"],
    )
    op.create_index(
        "ix_interview_coding_snapshots_user_id",
        "interview_coding_snapshots",
        ["user_id"],
    )
    op.create_table(
        "interview_coding_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("tests", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["interview_coding_snapshots.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "client_request_id"),
    )
    op.create_index(
        "ix_interview_coding_runs_session_id", "interview_coding_runs", ["session_id"]
    )
    op.create_index("ix_interview_coding_runs_user_id", "interview_coding_runs", ["user_id"])
    op.create_index(
        "ix_interview_coding_runs_snapshot_id", "interview_coding_runs", ["snapshot_id"]
    )
    op.create_index("ix_interview_coding_runs_status", "interview_coding_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_interview_coding_runs_status", table_name="interview_coding_runs")
    op.drop_index("ix_interview_coding_runs_snapshot_id", table_name="interview_coding_runs")
    op.drop_index("ix_interview_coding_runs_user_id", table_name="interview_coding_runs")
    op.drop_index("ix_interview_coding_runs_session_id", table_name="interview_coding_runs")
    op.drop_table("interview_coding_runs")
    op.drop_index("ix_interview_coding_snapshots_user_id", table_name="interview_coding_snapshots")
    op.drop_index(
        "ix_interview_coding_snapshots_session_id", table_name="interview_coding_snapshots"
    )
    op.drop_table("interview_coding_snapshots")
    op.drop_column("interview_reports", "coding_evidence")
    for table in ("interview_sessions", "training_drafts"):
        op.drop_constraint(f"ck_{table}_interview_type", table, type_="check")
        op.create_check_constraint(
            f"ck_{table}_interview_type",
            table,
            f"interview_type IN ({ORIGINAL_INTERVIEW_TYPES})",
        )

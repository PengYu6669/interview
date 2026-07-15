"""Create persisted system design board snapshots.

Revision ID: 20260715_0021
Revises: 20260715_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0021"
down_revision: str | None = "20260715_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "interview_board_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("client_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "revision"),
        sa.UniqueConstraint("user_id", "client_snapshot_id"),
    )
    op.create_index(
        "ix_interview_board_snapshots_session_id",
        "interview_board_snapshots",
        ["session_id"],
    )
    op.create_index(
        "ix_interview_board_snapshots_user_id",
        "interview_board_snapshots",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("interview_board_snapshots")

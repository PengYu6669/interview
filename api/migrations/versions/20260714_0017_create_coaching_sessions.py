"""创建专项训练会话。

Revision ID: 20260714_0017
Revises: 20260714_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0017"
down_revision: str | None = "20260714_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coaching_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("target_role", sa.String(150), nullable=False),
        sa.Column("training_goal", sa.String(500), nullable=False),
        sa.Column("skill_name", sa.String(64), nullable=False),
        sa.Column("skill_version", sa.String(30), nullable=False),
        sa.Column("task", postgresql.JSONB(), nullable=False),
        sa.Column("current_question", sa.Text(), nullable=True),
        sa.Column("source_ids", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "mode IN ('structured_expression', 'business_sense')",
            name="ck_coaching_sessions_mode",
        ),
        sa.CheckConstraint(
            "channel IN ('text', 'voice')", name="ck_coaching_sessions_channel"
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'active', 'completed')",
            name="ck_coaching_sessions_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coaching_sessions_user_id", "coaching_sessions", ["user_id"])
    op.create_index("ix_coaching_sessions_mode", "coaching_sessions", ["mode"])
    op.create_index("ix_coaching_sessions_status", "coaching_sessions", ["status"])

    op.create_table(
        "coaching_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("answer_mode", sa.String(20), nullable=False),
        sa.Column("decision", postgresql.JSONB(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "answer_mode IN ('text', 'voice')", name="ck_coaching_turns_answer_mode"
        ),
        sa.ForeignKeyConstraint(["session_id"], ["coaching_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "sequence"),
        sa.UniqueConstraint("session_id", "client_message_id"),
    )
    op.create_index("ix_coaching_turns_session_id", "coaching_turns", ["session_id"])
    op.create_index(
        "ix_coaching_turns_client_message_id", "coaching_turns", ["client_message_id"]
    )


def downgrade() -> None:
    op.drop_table("coaching_turns")
    op.drop_table("coaching_sessions")


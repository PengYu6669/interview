"""Create Agent tool audit records.

Revision ID: 20260714_0018
Revises: 20260714_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0018"
down_revision: str | None = "20260714_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tool_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_call_id", sa.String(200), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("argument_summary", postgresql.JSONB(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("duration_ms >= 0", name="ck_agent_tool_audits_duration"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tool_audits_user_id", "agent_tool_audits", ["user_id"])
    op.create_index("ix_agent_tool_audits_request_id", "agent_tool_audits", ["request_id"])
    op.create_index("ix_agent_tool_audits_session_id", "agent_tool_audits", ["session_id"])
    op.create_index("ix_agent_tool_audits_tool_name", "agent_tool_audits", ["tool_name"])
    op.create_index("ix_agent_tool_audits_created_at", "agent_tool_audits", ["created_at"])


def downgrade() -> None:
    op.drop_table("agent_tool_audits")

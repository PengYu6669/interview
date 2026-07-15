"""创建训练草稿表。

Revision ID: 20260712_0002
Revises: 20260712_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260712_0002"
down_revision: str | None = "20260712_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_filename", sa.String(length=255), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column("jd", sa.Text(), nullable=False),
        sa.Column("target_role", sa.String(length=150), nullable=False),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("extraction", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_drafts_user_id", "training_drafts", ["user_id"])
    op.create_index("ix_training_drafts_expires_at", "training_drafts", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_training_drafts_expires_at", table_name="training_drafts")
    op.drop_index("ix_training_drafts_user_id", table_name="training_drafts")
    op.drop_table("training_drafts")

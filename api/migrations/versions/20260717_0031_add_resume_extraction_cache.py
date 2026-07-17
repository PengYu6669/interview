"""add resume extraction cache

Revision ID: 20260717_0031
Revises: 20260717_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260717_0031"
down_revision: str | None = "20260717_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_extraction_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "fingerprint", name="uq_resume_cache_user_fingerprint"
        ),
    )
    op.create_index(
        "ix_resume_extraction_cache_user_id",
        "resume_extraction_cache",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resume_extraction_cache_user_id", table_name="resume_extraction_cache"
    )
    op.drop_table("resume_extraction_cache")

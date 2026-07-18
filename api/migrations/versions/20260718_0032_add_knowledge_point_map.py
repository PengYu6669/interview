"""add knowledge point map

Revision ID: 20260718_0032
Revises: 20260717_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0032"
down_revision: str | None = "20260717_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_documents",
        sa.Column("knowledge_point_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "question_documents",
        sa.Column(
            "covered_knowledge_point_count", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "question_documents",
        sa.Column("requested_question_limit", sa.Integer(), server_default="30", nullable=False),
    )
    op.create_table(
        "knowledge_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stable_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("knowledge_type", sa.String(length=30), nullable=False),
        sa.Column("interview_claim", sa.Text(), nullable=False),
        sa.Column("section_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("heading_paths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["question_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "stable_key"),
    )
    op.create_index("ix_knowledge_points_document_id", "knowledge_points", ["document_id"])
    op.create_index("ix_knowledge_points_knowledge_type", "knowledge_points", ["knowledge_type"])
    op.add_column(
        "questions", sa.Column("knowledge_point_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_questions_knowledge_point_id",
        "questions",
        "knowledge_points",
        ["knowledge_point_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_questions_knowledge_point_id", "questions", ["knowledge_point_id"])


def downgrade() -> None:
    op.drop_index("ix_questions_knowledge_point_id", table_name="questions")
    op.drop_constraint("fk_questions_knowledge_point_id", "questions", type_="foreignkey")
    op.drop_column("questions", "knowledge_point_id")
    op.drop_index("ix_knowledge_points_knowledge_type", table_name="knowledge_points")
    op.drop_index("ix_knowledge_points_document_id", table_name="knowledge_points")
    op.drop_table("knowledge_points")
    op.drop_column("question_documents", "requested_question_limit")
    op.drop_column("question_documents", "covered_knowledge_point_count")
    op.drop_column("question_documents", "knowledge_point_count")

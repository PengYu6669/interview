"""add question documents and career planning

Revision ID: 20260716_0026
Revises: 20260715_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0026"
down_revision: str | None = "20260715_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
        sa.Column("coverage_ratio", sa.Float(), nullable=False),
        sa.Column("section_count", sa.Integer(), nullable=False),
        sa.Column("covered_section_count", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "filename", "version"),
    )
    op.create_index(
        "ix_question_documents_owner_user_id", "question_documents", ["owner_user_id"]
    )
    op.create_index(
        "ix_question_documents_content_hash", "question_documents", ["content_hash"]
    )
    op.create_index("ix_question_documents_status", "question_documents", ["status"])

    op.add_column(
        "questions",
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "questions",
        sa.Column("framework", sa.String(30), nullable=False, server_default="technical"),
    )
    op.add_column(
        "questions", sa.Column("content_fingerprint", sa.String(64), nullable=True)
    )
    op.create_foreign_key(
        "fk_questions_source_document_id",
        "questions",
        "question_documents",
        ["source_document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_questions_source_document_id", "questions", ["source_document_id"])
    op.create_index("ix_questions_framework", "questions", ["framework"])
    op.create_index("ix_questions_content_fingerprint", "questions", ["content_fingerprint"])

    op.create_table(
        "question_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_key", sa.String(40), nullable=False),
        sa.Column("heading_path", postgresql.JSONB(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["question_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_evidence_question_id", "question_evidence", ["question_id"])
    op.create_index("ix_question_evidence_document_id", "question_evidence", ["document_id"])

    op.create_table(
        "career_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_role", sa.String(150), nullable=False),
        sa.Column("target_level", sa.String(50), nullable=False),
        sa.Column("target_companies", postgresql.JSONB(), nullable=False),
        sa.Column("preferred_cities", postgresql.JSONB(), nullable=False),
        sa.Column("weekly_hours", sa.Integer(), nullable=False),
        sa.Column("constraints", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "weekly_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("goal", sa.String(500), nullable=False),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "week_start"),
    )
    op.create_index("ix_weekly_plans_user_id", "weekly_plans", ["user_id"])
    op.create_index("ix_weekly_plans_week_start", "weekly_plans", ["week_start"])


def downgrade() -> None:
    op.drop_table("weekly_plans")
    op.drop_table("career_profiles")
    op.drop_table("question_evidence")
    op.drop_index("ix_questions_content_fingerprint", table_name="questions")
    op.drop_index("ix_questions_framework", table_name="questions")
    op.drop_index("ix_questions_source_document_id", table_name="questions")
    op.drop_constraint("fk_questions_source_document_id", "questions", type_="foreignkey")
    op.drop_column("questions", "content_fingerprint")
    op.drop_column("questions", "framework")
    op.drop_column("questions", "source_document_id")
    op.drop_table("question_documents")

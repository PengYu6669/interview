"""扩展题库编辑、导入与问答。

Revision ID: 20260713_0004
Revises: 20260713_0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260713_0004"
down_revision: str | None = "20260713_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "questions", sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "questions", sa.Column("content_markdown", sa.Text(), nullable=False, server_default="")
    )
    op.add_column("questions", sa.Column("source_document_name", sa.String(255), nullable=True))
    op.create_foreign_key(
        "fk_questions_owner", "questions", "users", ["owner_user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_questions_owner_user_id", "questions", ["owner_user_id"])
    op.create_table(
        "question_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_title", sa.String(250), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_chunks_question_id", "question_chunks", ["question_id"])
    op.create_table(
        "question_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_conversations_user_id", "question_conversations", ["user_id"])
    op.create_index(
        "ix_question_conversations_question_id", "question_conversations", ["question_id"]
    )
    op.create_table(
        "question_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["question_conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_question_messages_conversation_id", "question_messages", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_table("question_messages")
    op.drop_table("question_conversations")
    op.drop_table("question_chunks")
    op.drop_index("ix_questions_owner_user_id", table_name="questions")
    op.drop_constraint("fk_questions_owner", "questions", type_="foreignkey")
    op.drop_column("questions", "source_document_name")
    op.drop_column("questions", "content_markdown")
    op.drop_column("questions", "owner_user_id")

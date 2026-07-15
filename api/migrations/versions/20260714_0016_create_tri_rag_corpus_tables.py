"""创建三角 RAG 语料表。

Revision ID: 20260714_0016
Revises: 20260714_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0016"
down_revision: str | None = "20260714_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rag_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("corpus_type", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("quality_warnings", postgresql.JSONB(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "corpus_type IN ('candidate', 'job', 'knowledge')",
            name="ck_rag_documents_corpus_type",
        ),
        sa.CheckConstraint(
            "visibility IN ('private', 'public')", name="ck_rag_documents_visibility"
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id", "source_type", "source_id", name="uq_rag_document_source"
        ),
    )
    op.create_index("ix_rag_documents_owner_user_id", "rag_documents", ["owner_user_id"])
    op.create_index("ix_rag_documents_corpus_type", "rag_documents", ["corpus_type"])
    op.create_index("ix_rag_documents_source_type", "rag_documents", ["source_type"])
    op.create_index("ix_rag_documents_source_id", "rag_documents", ["source_id"])
    op.create_index("ix_rag_documents_visibility", "rag_documents", ["visibility"])
    op.create_index("ix_rag_documents_content_hash", "rag_documents", ["content_hash"])

    op.create_table(
        "rag_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corpus_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("heading_path", postgresql.JSONB(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "corpus_type IN ('candidate', 'job', 'knowledge')",
            name="ck_rag_chunks_corpus_type",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["rag_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    op.create_index("ix_rag_chunks_document_id", "rag_chunks", ["document_id"])
    op.create_index("ix_rag_chunks_corpus_type", "rag_chunks", ["corpus_type"])
    op.create_index("ix_rag_chunks_content_hash", "rag_chunks", ["content_hash"])
    op.execute(
        "CREATE INDEX ix_rag_chunks_search_vector ON rag_chunks "
        "USING gin (to_tsvector('simple', content))"
    )
    op.execute(
        "CREATE INDEX ix_rag_chunks_content_trgm ON rag_chunks "
        "USING gin (content gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_table("rag_chunks")
    op.drop_table("rag_documents")


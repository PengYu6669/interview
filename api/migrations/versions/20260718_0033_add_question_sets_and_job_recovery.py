"""add question sets and recoverable jobs

Revision ID: 20260718_0033
Revises: 20260718_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0033"
down_revision: str | None = "20260718_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_jobs",
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("ai_jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
    op.add_column(
        "ai_jobs",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_ai_jobs_heartbeat_at", "ai_jobs", ["heartbeat_at"])
    op.create_table(
        "question_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True)),
        sa.Column("name", sa.String(250), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["question_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_question_sets_owner_user_id", "question_sets", ["owner_user_id"])
    op.create_index("ix_question_sets_document_id", "question_sets", ["document_id"])
    op.create_index("ix_question_sets_kind", "question_sets", ["kind"])
    op.create_index("ix_question_sets_status", "question_sets", ["status"])
    op.create_table(
        "question_set_items",
        sa.Column("question_set_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["question_set_id"], ["question_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("question_set_id", "question_id"),
    )
    op.create_index("ix_question_set_items_question_id", "question_set_items", ["question_id"])
    op.execute(
        """
        INSERT INTO question_sets
            (id, owner_user_id, document_id, name, kind, status,
             target_count, created_at, updated_at)
        SELECT gen_random_uuid(), owner_user_id, id, filename, 'default',
               CASE WHEN status = 'ready' THEN 'ready' ELSE 'failed' END,
               0, created_at, updated_at
        FROM question_documents
        """
    )
    op.execute(
        """
        INSERT INTO question_set_items (question_set_id, question_id, sort_order, created_at)
        SELECT s.id, q.id,
               row_number() OVER (PARTITION BY s.id ORDER BY q.created_at)::integer,
               q.created_at
        FROM question_sets s
        JOIN questions q ON q.source_document_id = s.document_id
        WHERE s.kind = 'default'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_question_set_items_question_id", table_name="question_set_items")
    op.drop_table("question_set_items")
    op.drop_index("ix_question_sets_status", table_name="question_sets")
    op.drop_index("ix_question_sets_kind", table_name="question_sets")
    op.drop_index("ix_question_sets_document_id", table_name="question_sets")
    op.drop_index("ix_question_sets_owner_user_id", table_name="question_sets")
    op.drop_table("question_sets")
    op.drop_index("ix_ai_jobs_heartbeat_at", table_name="ai_jobs")
    op.drop_column("ai_jobs", "attempt_count")
    op.drop_column("ai_jobs", "heartbeat_at")
    op.drop_column("ai_jobs", "payload")

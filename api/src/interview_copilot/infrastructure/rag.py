from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from interview_copilot.infrastructure.database import Base
from interview_copilot.infrastructure.questions import json_type


class RagDocumentRecord(Base):
    __tablename__ = "rag_documents"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "source_type",
            "source_id",
            name="uq_rag_document_source",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    corpus_type: Mapped[str] = mapped_column(String(20), index=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[UUID | None] = mapped_column(nullable=True, index=True)
    visibility: Mapped[str] = mapped_column(String(20), default="private", index=True)
    title: Mapped[str] = mapped_column(String(250))
    normalized_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    quality_warnings: Mapped[list[str]] = mapped_column(json_type, default=list)
    source_metadata: Mapped[dict] = mapped_column("metadata", json_type, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    chunks: Mapped[list["RagChunkRecord"]] = relationship(cascade="all, delete-orphan")


class RagChunkRecord(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("rag_documents.id", ondelete="CASCADE"), index=True
    )
    corpus_type: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    heading_path: Mapped[list[str]] = mapped_column(json_type, default=list)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

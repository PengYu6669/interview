from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from interview_copilot.infrastructure.database import Base

json_type = JSON().with_variant(JSONB, "postgresql")


class TopicRecord(Base):
    __tablename__ = "question_topics"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))


class QuestionDocumentRecord(Base):
    __tablename__ = "question_documents"
    __table_args__ = (UniqueConstraint("owner_user_id", "filename", "version"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(120))
    normalized_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="ready", index=True)
    warnings: Mapped[list[str]] = mapped_column(json_type, default=list)
    coverage_ratio: Mapped[float] = mapped_column(Float, default=0)
    section_count: Mapped[int] = mapped_column(Integer, default=0)
    covered_section_count: Mapped[int] = mapped_column(Integer, default=0)
    knowledge_point_count: Mapped[int] = mapped_column(Integer, default=0)
    covered_knowledge_point_count: Mapped[int] = mapped_column(Integer, default=0)
    requested_question_limit: Mapped[int] = mapped_column(Integer, default=30)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    questions: Mapped[list["QuestionRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    knowledge_points: Mapped[list["KnowledgePointRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    question_sets: Mapped[list["QuestionSetRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class QuestionSetRecord(Base):
    __tablename__ = "question_sets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("question_documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(250))
    kind: Mapped[str] = mapped_column(String(20), default="custom", index=True)
    status: Mapped[str] = mapped_column(String(20), default="ready", index=True)
    target_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    document: Mapped[QuestionDocumentRecord | None] = relationship(back_populates="question_sets")
    items: Mapped[list["QuestionSetItemRecord"]] = relationship(
        back_populates="question_set", cascade="all, delete-orphan"
    )


class QuestionSetItemRecord(Base):
    __tablename__ = "question_set_items"
    __table_args__ = (UniqueConstraint("question_set_id", "question_id"),)

    question_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("question_sets.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    question_set: Mapped[QuestionSetRecord] = relationship(back_populates="items")
    question: Mapped["QuestionRecord"] = relationship()


class KnowledgePointRecord(Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (UniqueConstraint("document_id", "stable_key"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("question_documents.id", ondelete="CASCADE"), index=True
    )
    stable_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(250))
    knowledge_type: Mapped[str] = mapped_column(String(30), index=True)
    interview_claim: Mapped[str] = mapped_column(Text)
    section_keys: Mapped[list[str]] = mapped_column(json_type, default=list)
    heading_paths: Mapped[list[list[str]]] = mapped_column(json_type, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    document: Mapped[QuestionDocumentRecord] = relationship(back_populates="knowledge_points")
    questions: Mapped[list["QuestionRecord"]] = relationship(back_populates="knowledge_point")


class QuestionRecord(Base):
    __tablename__ = "questions"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(250))
    prompt: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20), index=True)
    question_type: Mapped[str] = mapped_column(String(30), index=True)
    intent: Mapped[str] = mapped_column(Text)
    answer_outline: Mapped[list[str]] = mapped_column(json_type)
    common_mistakes: Mapped[list[str]] = mapped_column(json_type)
    published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    source_document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("question_documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    knowledge_point_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True, index=True
    )
    framework: Mapped[str] = mapped_column(String(30), default="technical", index=True)
    content_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    document: Mapped[QuestionDocumentRecord | None] = relationship(back_populates="questions")
    knowledge_point: Mapped[KnowledgePointRecord | None] = relationship(back_populates="questions")
    topics: Mapped[list[TopicRecord]] = relationship(secondary="question_topic_links")
    sources: Mapped[list["QuestionSourceRecord"]] = relationship(cascade="all, delete-orphan")
    evidence: Mapped[list["QuestionEvidenceRecord"]] = relationship(cascade="all, delete-orphan")


class QuestionTopicLink(Base):
    __tablename__ = "question_topic_links"
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[UUID] = mapped_column(
        ForeignKey("question_topics.id", ondelete="CASCADE"), primary_key=True
    )


class QuestionSourceRecord(Base):
    __tablename__ = "question_sources"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(250))
    url: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(120))


class QuestionEvidenceRecord(Base):
    __tablename__ = "question_evidence"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("question_documents.id", ondelete="CASCADE"), index=True
    )
    section_key: Mapped[str] = mapped_column(String(40))
    heading_path: Mapped[list[str]] = mapped_column(json_type, default=list)
    quote: Mapped[str] = mapped_column(Text)


class UserQuestionProgressRecord(Base):
    __tablename__ = "user_question_progress"
    __table_args__ = (UniqueConstraint("user_id", "question_id"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="unseen")
    bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)
    review_interval_days: Mapped[int] = mapped_column(default=0)
    review_streak: Mapped[int] = mapped_column(default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserQuestionNoteRecord(Base):
    __tablename__ = "user_question_notes"
    __table_args__ = (UniqueConstraint("user_id", "question_id"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionChunkRecord(Base):
    __tablename__ = "question_chunks"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(String(250))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[int] = mapped_column(default=0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)


class QuestionConversationRecord(Base):
    __tablename__ = "question_conversations"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionMessageRecord(Base):
    __tablename__ = "question_messages"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("question_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[dict]] = mapped_column(json_type, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

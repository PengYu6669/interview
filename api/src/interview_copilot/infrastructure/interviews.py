from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
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
from sqlalchemy.orm import Mapped, mapped_column

from interview_copilot.infrastructure.database import Base

json_type = JSON().with_variant(JSONB, "postgresql")


class InterviewSessionRecord(Base):
    __tablename__ = "interview_sessions"
    __table_args__ = (UniqueConstraint("draft_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("training_drafts.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    target_role: Mapped[str] = mapped_column(String(150))
    target_company: Mapped[str] = mapped_column(String(100), default="")
    target_level: Mapped[str] = mapped_column(String(30), default="campus")
    interview_round: Mapped[str] = mapped_column(String(30), default="first")
    interview_type: Mapped[str] = mapped_column(String(30), default="comprehensive")
    mode: Mapped[str] = mapped_column(String(30))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    pressure_level: Mapped[int] = mapped_column(Integer, default=3)
    depth_level: Mapped[int] = mapped_column(Integer, default=4)
    guidance_level: Mapped[int] = mapped_column(Integer, default=2)
    training_focus: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(Text)
    plan: Mapped[dict] = mapped_column(json_type)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    current_phase_index: Mapped[int] = mapped_column(Integer, default=0)
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accumulated_pause_seconds: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_status: Mapped[str] = mapped_column(String(20), default="not_started", index=True)
    report_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    report_generation_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    report_generation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    report_generation_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)


class InterviewTurnRecord(Base):
    __tablename__ = "interview_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence"),
        UniqueConstraint("session_id", "client_message_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    client_message_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    sequence: Mapped[int] = mapped_column(Integer)
    phase_index: Mapped[int] = mapped_column(Integer)
    question_index: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    answer_mode: Mapped[str] = mapped_column(String(20))
    decision: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str] = mapped_column(Text)
    transition: Mapped[str] = mapped_column(String(120))
    interviewer_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InterviewReportRecord(Base):
    __tablename__ = "interview_reports"
    __table_args__ = (UniqueConstraint("session_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[dict] = mapped_column(json_type)
    verification_status: Mapped[str] = mapped_column(String(20), default="not_run")
    verification_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verified_claims: Mapped[list[dict]] = mapped_column(json_type, default=list)
    board_snapshot: Mapped[dict | None] = mapped_column(json_type, nullable=True)
    coding_evidence: Mapped[list[dict]] = mapped_column(json_type, default=list)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    rubric_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InterviewReportReviewRecord(Base):
    __tablename__ = "interview_report_reviews"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "client_request_id",
            name="uq_interview_report_reviews_user_request",
        ),
        CheckConstraint("skill_index >= 0", name="ck_interview_report_reviews_skill_index"),
        CheckConstraint(
            "original_score >= 0 AND original_score <= 100",
            name="ck_interview_report_reviews_original_score",
        ),
        CheckConstraint(
            "revised_score IS NULL OR (revised_score >= 0 AND revised_score <= 100)",
            name="ck_interview_report_reviews_revised_score",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_reports.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    client_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    skill_index: Mapped[int] = mapped_column(Integer)
    skill: Mapped[str] = mapped_column(String(80))
    original_score: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    revised_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

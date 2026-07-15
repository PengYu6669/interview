from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from interview_copilot.infrastructure.database import Base

json_type = JSON().with_variant(JSONB, "postgresql")


class InterviewCodingSnapshotRecord(Base):
    __tablename__ = "interview_coding_snapshots"
    __table_args__ = (
        UniqueConstraint("session_id", "phase_index", "question_index", "revision"),
        UniqueConstraint("user_id", "client_snapshot_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    phase_index: Mapped[int] = mapped_column(Integer)
    question_index: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    client_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    source: Mapped[str] = mapped_column(Text)
    complexity_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InterviewCodingRunRecord(Base):
    __tablename__ = "interview_coding_runs"
    __table_args__ = (UniqueConstraint("user_id", "client_request_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_coding_snapshots.id", ondelete="CASCADE"), index=True
    )
    client_request_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(30), index=True)
    tests: Mapped[list[dict]] = mapped_column(json_type, default=list)
    duration_ms: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

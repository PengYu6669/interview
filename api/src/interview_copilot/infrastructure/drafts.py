from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, delete, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from interview_copilot.infrastructure.database import Base


class TrainingDraftRecord(Base):
    __tablename__ = "training_drafts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    resume_filename: Mapped[str] = mapped_column(String(255))
    resume_text: Mapped[str] = mapped_column(Text)
    jd: Mapped[str] = mapped_column(Text, default="")
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
    source_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    career_plan_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("weekly_plan_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    extraction: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TrainingDraftQuestionRecord(Base):
    __tablename__ = "training_draft_questions"

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("training_drafts.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), primary_key=True
    )


def get_owned_draft(session: Session, draft_id: UUID, user_id: UUID) -> TrainingDraftRecord | None:
    return session.scalar(
        select(TrainingDraftRecord).where(
            TrainingDraftRecord.id == draft_id,
            TrainingDraftRecord.user_id == user_id,
            TrainingDraftRecord.expires_at > datetime.now().astimezone(),
        )
    )


def delete_expired_drafts(session: Session) -> int:
    expired = session.scalars(
        select(TrainingDraftRecord.id).where(
            TrainingDraftRecord.expires_at <= datetime.now().astimezone()
        )
    ).all()
    session.execute(delete(TrainingDraftRecord).where(TrainingDraftRecord.id.in_(expired)))
    session.commit()
    return len(expired)

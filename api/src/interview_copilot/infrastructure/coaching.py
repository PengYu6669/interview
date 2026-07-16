from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from interview_copilot.infrastructure.database import Base
from interview_copilot.infrastructure.questions import json_type


class CoachingSessionRecord(Base):
    __tablename__ = "coaching_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(40), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    target_role: Mapped[str] = mapped_column(String(150))
    training_goal: Mapped[str] = mapped_column(String(500), default="")
    skill_name: Mapped[str] = mapped_column(String(64))
    skill_version: Mapped[str] = mapped_column(String(30))
    task: Mapped[dict] = mapped_column(json_type)
    current_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ids: Mapped[list[str]] = mapped_column(json_type, default=list)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    career_plan_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("weekly_plan_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    turns: Mapped[list["CoachingTurnRecord"]] = relationship(cascade="all, delete-orphan")


class CoachingTurnRecord(Base):
    __tablename__ = "coaching_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence"),
        UniqueConstraint("session_id", "client_message_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("coaching_sessions.id", ondelete="CASCADE"), index=True
    )
    client_message_id: Mapped[UUID] = mapped_column(index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    answer: Mapped[str] = mapped_column(Text)
    answer_mode: Mapped[str] = mapped_column(String(20))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[dict] = mapped_column(json_type)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from interview_copilot.infrastructure.database import Base
from interview_copilot.infrastructure.questions import json_type


class CareerProfileRecord(Base):
    __tablename__ = "career_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    target_role: Mapped[str] = mapped_column(String(150), default="")
    target_level: Mapped[str] = mapped_column(String(50), default="")
    target_companies: Mapped[list[str]] = mapped_column(json_type, default=list)
    preferred_cities: Mapped[list[str]] = mapped_column(json_type, default=list)
    weekly_hours: Mapped[int] = mapped_column(Integer, default=5)
    available_weekdays: Mapped[list[int]] = mapped_column(
        json_type, default=lambda: [0, 2, 4, 5]
    )
    preferred_time_slot: Mapped[str] = mapped_column(String(20), default="evening")
    constraints: Mapped[str] = mapped_column(Text, default="")
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WeeklyPlanRecord(Base):
    __tablename__ = "weekly_plans"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    week_start: Mapped[date] = mapped_column(Date, index=True)
    goal: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="active")
    basis: Mapped[dict[str, object]] = mapped_column(json_type, default=dict)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    skill_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["WeeklyPlanItemRecord"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="WeeklyPlanItemRecord.position",
    )


class WeeklyPlanItemRecord(Base):
    __tablename__ = "weekly_plan_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("weekly_plans.id", ondelete="CASCADE"), index=True
    )
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    time_slot: Mapped[str] = mapped_column(String(20), default="flexible")
    scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=20)
    task_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    completion_criteria: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    origin: Mapped[str] = mapped_column(String(20), default="manual")
    question_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    coaching_mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    exercise_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    plan: Mapped[WeeklyPlanRecord] = relationship(back_populates="items")


class CareerPlanDraftRecord(Base):
    __tablename__ = "career_plan_drafts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    payload: Mapped[dict[str, object]] = mapped_column(json_type)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

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
    items: Mapped[list[dict[str, object]]] = mapped_column(json_type, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

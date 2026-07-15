from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CareerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_role: str = Field(default="", max_length=150)
    target_level: str = Field(default="", max_length=50)
    target_companies: list[str] = Field(default_factory=list, max_length=20)
    preferred_cities: list[str] = Field(default_factory=list, max_length=20)
    weekly_hours: int = Field(default=5, ge=1, le=80)
    constraints: str = Field(default="", max_length=2_000)
    confirmed_at: datetime | None = None
    updated_at: datetime | None = None


class WeeklyPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    category: Literal["learning", "interview", "resume", "application"]
    title: str = Field(min_length=1, max_length=200)
    target_count: int = Field(default=1, ge=1, le=100)
    completed_count: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_progress(self) -> "WeeklyPlanItem":
        if self.completed_count > self.target_count:
            raise ValueError("完成数量不能超过目标数量")
        return self


class WeeklyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    week_start: date
    goal: str = Field(min_length=1, max_length=500)
    items: list[WeeklyPlanItem] = Field(min_length=1, max_length=20)
    status: Literal["active", "completed", "archived"] = "active"
    created_at: datetime
    updated_at: datetime


class CareerWorkspace(BaseModel):
    profile: CareerProfile
    weekly_plan: WeeklyPlan | None
    suggested_focus: str | None = None

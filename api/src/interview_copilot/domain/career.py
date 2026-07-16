from datetime import date, datetime, time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CareerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_role: str = Field(default="", max_length=150)
    target_level: str = Field(default="", max_length=50)
    target_companies: list[str] = Field(default_factory=list, max_length=20)
    preferred_cities: list[str] = Field(default_factory=list, max_length=20)
    weekly_hours: int = Field(default=5, ge=1, le=80)
    available_weekdays: list[Annotated[int, Field(ge=0, le=6)]] = Field(
        default_factory=lambda: [0, 2, 4, 5], min_length=1, max_length=7
    )
    preferred_time_slot: Literal["morning", "afternoon", "evening", "flexible"] = (
        "evening"
    )
    constraints: str = Field(default="", max_length=2_000)
    confirmed_at: datetime | None = None
    updated_at: datetime | None = None


class WeeklyPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    scheduled_date: date
    time_slot: Literal["morning", "afternoon", "evening", "flexible"] = "flexible"
    scheduled_time: time | None = None
    estimated_minutes: int = Field(default=20, ge=5, le=240)
    task_type: Literal[
        "question_review",
        "structured_expression",
        "business_sense",
        "mock_interview",
        "resume",
        "application",
    ]
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=600)
    completion_criteria: str = Field(min_length=1, max_length=500)
    status: Literal["pending", "in_progress", "completed", "skipped"] = "pending"
    origin: Literal["ai", "manual", "migrated"] = "manual"
    question_id: UUID | None = None
    question_slug: str | None = Field(default=None, max_length=150)
    coaching_mode: Literal["structured_expression", "business_sense"] | None = None
    exercise_type: str | None = Field(default=None, max_length=40)
    difficulty: Literal["guided", "assisted", "pressure"] | None = None
    position: int = Field(default=0, ge=0, le=100)
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_training_link(self) -> "WeeklyPlanItem":
        if self.task_type in {"structured_expression", "business_sense"} and (
            not self.coaching_mode or not self.exercise_type or not self.difficulty
        ):
            raise ValueError("专项训练事项缺少训练模式、题型或难度")
        if self.question_id and self.task_type not in {
            "question_review",
            "structured_expression",
        }:
            raise ValueError("只有题目学习或结构化表达事项可以关联题目")
        return self


class CareerQuestionOption(BaseModel):
    id: UUID
    slug: str
    title: str
    difficulty: str
    framework: str
    topics: list[str] = Field(default_factory=list)
    source_document_name: str | None = None
    review_due: bool = False
    owned: bool = False


class PlanningBasis(BaseModel):
    profile_confirmed: bool
    question_count: int = Field(ge=0)
    owned_question_count: int = Field(ge=0)
    due_question_count: int = Field(ge=0)
    recent_training_count: int = Field(ge=0)
    evidence_focus: str | None = None


class WeeklyPlanDraft(BaseModel):
    id: UUID
    week_start: date
    goal: str = Field(min_length=1, max_length=500)
    items: list[WeeklyPlanItem] = Field(min_length=1, max_length=20)
    basis: PlanningBasis
    model: str
    prompt_version: str
    skill_version: str
    expires_at: datetime


class WeeklyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    week_start: date
    goal: str = Field(min_length=1, max_length=500)
    items: list[WeeklyPlanItem] = Field(min_length=1, max_length=20)
    status: Literal["active", "completed", "archived"] = "active"
    basis: PlanningBasis
    model: str | None = None
    prompt_version: str | None = None
    skill_version: str | None = None
    confirmed_at: datetime
    created_at: datetime
    updated_at: datetime


class CareerWorkspace(BaseModel):
    profile: CareerProfile
    weekly_plan: WeeklyPlan | None
    plan_history: list[WeeklyPlan] = Field(default_factory=list)
    question_options: list[CareerQuestionOption] = Field(default_factory=list)

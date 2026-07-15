from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CoachingMode = Literal["structured_expression", "business_sense"]
CoachingChannel = Literal["text", "voice"]
CoachingStatus = Literal["planned", "active", "completed"]
CoachingAction = Literal["follow_up", "retry", "complete"]


class CoachingTaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=500)
    scenario: str = Field(min_length=1, max_length=3_000)
    primary_question: str = Field(min_length=1, max_length=1_500)
    estimated_minutes: int = Field(ge=5, le=30)
    dimensions: list[str] = Field(min_length=2, max_length=7)


class DimensionAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=60)
    status: Literal["observed", "evidence_insufficient"]
    level: int | None = Field(
        ge=1,
        le=5,
        description="status=observed 时为 1 至 5；status=evidence_insufficient 时必须为 null",
    )
    evidence_quote: str | None = Field(
        max_length=500,
        description="status=observed 时逐字引用用户回答；证据不足时必须为 null",
    )
    feedback: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_evidence(self) -> "DimensionAssessment":
        if self.status == "observed" and (self.level is None or not self.evidence_quote):
            raise ValueError("已观察维度必须包含等级和回答证据")
        if self.status == "evidence_insufficient" and (
            self.level is not None or self.evidence_quote is not None
        ):
            raise ValueError("证据不足时不能给出等级或伪造证据")
        return self


class CoachingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: CoachingAction
    coach_reply: str = Field(min_length=1, max_length=1_000)
    next_question: str | None = Field(default=None, max_length=1_500)
    assessments: list[DimensionAssessment] = Field(min_length=1, max_length=7)
    summary: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_next_question(self) -> "CoachingDecision":
        if self.action == "complete" and self.next_question is not None:
            raise ValueError("训练完成后不能继续提问")
        if self.action != "complete" and not self.next_question:
            raise ValueError("继续训练时必须给出下一个问题")
        return self


class CoachingTurnData(BaseModel):
    id: UUID
    sequence: int
    answer: str
    answer_mode: CoachingChannel
    decision: CoachingDecision
    created_at: datetime


class CoachingSessionData(BaseModel):
    id: UUID
    mode: CoachingMode
    channel: CoachingChannel
    status: CoachingStatus
    target_role: str
    training_goal: str
    skill_name: str
    skill_version: str
    task: CoachingTaskPlan
    current_question: str | None
    turns: list[CoachingTurnData]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class CoachingSessionSummary(BaseModel):
    id: UUID
    mode: CoachingMode
    channel: CoachingChannel
    status: CoachingStatus
    title: str
    target_role: str
    current_question: str | None
    turn_count: int = Field(ge=0)
    updated_at: datetime

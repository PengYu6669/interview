from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from interview_copilot.domain.coaching import CoachingMode


class AbilityKlinePoint(BaseModel):
    session_id: UUID
    date: datetime
    open: int = Field(ge=0, le=100)
    high: int = Field(ge=0, le=100)
    low: int = Field(ge=0, le=100)
    close: int = Field(ge=0, le=100)
    evidence_coverage: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)


class AbilityMatrixItem(BaseModel):
    skill: str
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    evidence_count: int = Field(ge=1)
    report_count: int = Field(ge=1)
    trend: int = Field(ge=-100, le=100)
    source_session_id: UUID
    training_focus: str = Field(min_length=1, max_length=500)


class CoachingAbilityItem(BaseModel):
    dimension: str
    mode: CoachingMode
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    evidence_count: int = Field(ge=1)
    session_count: int = Field(ge=1)
    source_session_id: UUID
    latest_feedback: str = Field(min_length=1, max_length=500)


class CoachingProfileSummary(BaseModel):
    session_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    skills: list[CoachingAbilityItem]
    next_mode: CoachingMode | None
    next_focus: str | None


class AbilityProfileData(BaseModel):
    report_count: int
    average_score: int | None
    average_coverage: int | None
    kline: list[AbilityKlinePoint]
    skills: list[AbilityMatrixItem]
    next_training: str | None
    coaching: CoachingProfileSummary

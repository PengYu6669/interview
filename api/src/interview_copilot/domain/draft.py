from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .resume import ResumeProfile
from .training import InterviewRound, InterviewType, TargetLevel


class TrainingDraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    resume_filename: str = Field(max_length=255)
    resume_text: str = Field(max_length=80_000)
    jd: str = Field(max_length=30_000)
    target_role: str = Field(max_length=150)
    target_company: str = Field(default="", max_length=100)
    target_level: TargetLevel = "campus"
    interview_round: InterviewRound = "first"
    interview_type: InterviewType = "comprehensive"
    mode: str = Field(max_length=30)
    duration_minutes: int = Field(ge=1, le=180)
    pressure_level: int = Field(ge=1, le=5)
    depth_level: int = Field(ge=1, le=5)
    guidance_level: int = Field(ge=1, le=5)
    question_ids: list[UUID] = Field(default_factory=list, max_length=20)
    training_focus: str = Field(default="", max_length=500)
    extraction: ResumeProfile | None = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

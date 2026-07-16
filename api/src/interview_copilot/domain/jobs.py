from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AiJobStatus(BaseModel):
    id: UUID
    kind: Literal["question_import", "career_plan"]
    status: Literal["queued", "processing", "completed", "failed"]
    stage: str
    progress: int = Field(ge=0, le=100)
    estimated_seconds: int = Field(ge=0)
    resource_id: UUID | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

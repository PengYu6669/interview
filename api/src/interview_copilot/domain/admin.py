from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AdminUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    role: str
    created_at: datetime


class AdminSystemLog(BaseModel):
    id: UUID
    request_id: UUID
    session_id: UUID | None
    tool_name: str
    succeeded: bool
    duration_ms: int
    error_type: str | None
    created_at: datetime

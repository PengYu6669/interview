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


class AdminUserMetrics(BaseModel):
    total_users: int
    daily_active_users: int
    weekly_active_users: int
    new_users_today: int
    admin_users: int
    timezone: str = "Asia/Shanghai"


class AdminUserList(BaseModel):
    metrics: AdminUserMetrics
    users: list[AdminUserSummary]


class AdminSystemLog(BaseModel):
    id: UUID
    request_id: UUID
    session_id: UUID | None
    tool_name: str
    succeeded: bool
    duration_ms: int
    error_type: str | None
    created_at: datetime

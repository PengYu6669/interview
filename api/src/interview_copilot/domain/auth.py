from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str
    created_at: datetime


class AuthResult(BaseModel):
    user: UserProfile
    session_token: str
    expires_at: datetime

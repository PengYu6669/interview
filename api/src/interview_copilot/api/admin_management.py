from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_admin
from interview_copilot.application.admin_management import AdminManagementService
from interview_copilot.domain.admin import AdminSystemLog, AdminUserSummary
from interview_copilot.domain.auth import UserProfile
from interview_copilot.infrastructure.database import get_database_session

router = APIRouter(prefix="/v1/admin", tags=["admin-management"])


def admin_management_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AdminManagementService:
    return AdminManagementService(session)


@router.get("/users", response_model=list[AdminUserSummary])
def list_admin_users(
    _admin: Annotated[UserProfile, Depends(require_admin)],
    service: Annotated[AdminManagementService, Depends(admin_management_service)],
    query: str = Query(default="", max_length=100),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[AdminUserSummary]:
    return service.list_users(query=query, limit=limit)


@router.get("/logs", response_model=list[AdminSystemLog])
def list_admin_logs(
    _admin: Annotated[UserProfile, Depends(require_admin)],
    service: Annotated[AdminManagementService, Depends(admin_management_service)],
    limit: int = Query(default=100, ge=1, le=200),
) -> list[AdminSystemLog]:
    return service.list_logs(limit=limit)

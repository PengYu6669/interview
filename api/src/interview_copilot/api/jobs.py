from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.jobs import AiJobService
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.jobs import AiJobStatus
from interview_copilot.infrastructure.database import get_database_session

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.get("/latest", response_model=AiJobStatus | None)
def latest_job(
    kind: Annotated[Literal["question_import", "career_plan"], Query()],
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> AiJobStatus | None:
    return AiJobService(session).latest(user_id=user.id, kind=kind)


@router.get("/{job_id}", response_model=AiJobStatus)
def get_job(
    job_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> AiJobStatus:
    try:
        return AiJobService(session).get(user_id=user.id, job_id=job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

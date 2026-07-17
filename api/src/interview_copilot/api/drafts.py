from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.drafts import DraftLockedError, DraftService
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.draft import TrainingDraftData, TrainingDraftSummary
from interview_copilot.domain.resume import ResumeProfile
from interview_copilot.domain.training import InterviewRound, InterviewType, TargetLevel
from interview_copilot.infrastructure.database import get_database_session

router = APIRouter(prefix="/v1/drafts", tags=["drafts"])


class DraftCreateRequest(BaseModel):
    resume_filename: str = Field(max_length=255)
    resume_text: str = Field(min_length=1, max_length=80_000)
    jd: str = Field(max_length=30_000)
    target_role: str = Field(min_length=1, max_length=150)
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
    source_session_id: UUID | None = None
    career_plan_item_id: UUID | None = None


class DraftUpdateRequest(BaseModel):
    resume_filename: str | None = Field(default=None, max_length=255)
    resume_text: str | None = Field(default=None, min_length=1, max_length=80_000)
    jd: str | None = Field(default=None, max_length=30_000)
    target_role: str | None = Field(default=None, min_length=1, max_length=150)
    target_company: str | None = Field(default=None, max_length=100)
    target_level: TargetLevel | None = None
    interview_round: InterviewRound | None = None
    interview_type: InterviewType | None = None
    mode: str | None = Field(default=None, max_length=30)
    duration_minutes: int | None = Field(default=None, ge=1, le=180)
    pressure_level: int | None = Field(default=None, ge=1, le=5)
    depth_level: int | None = Field(default=None, ge=1, le=5)
    guidance_level: int | None = Field(default=None, ge=1, le=5)
    question_ids: list[UUID] | None = Field(default=None, max_length=20)
    training_focus: str | None = Field(default=None, max_length=500)
    source_session_id: UUID | None = None
    career_plan_item_id: UUID | None = None
    extraction: ResumeProfile | None = None


def draft_service(session: Annotated[Session, Depends(get_database_session)]) -> DraftService:
    return DraftService(session, retention_days=7)


@router.post("", response_model=TrainingDraftData, status_code=201)
def create_draft(
    request: DraftCreateRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[DraftService, Depends(draft_service)],
) -> TrainingDraftData:
    try:
        return service.create(user_id=user.id, data=request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[TrainingDraftSummary])
def list_resumable_drafts(
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[DraftService, Depends(draft_service)],
) -> list[TrainingDraftSummary]:
    return service.list_resumable(user_id=user.id)


@router.get("/{draft_id}", response_model=TrainingDraftData)
def get_draft(
    draft_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[DraftService, Depends(draft_service)],
) -> TrainingDraftData:
    try:
        return service.get(user_id=user.id, draft_id=draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{draft_id}", response_model=TrainingDraftData)
def update_draft(
    draft_id: UUID,
    request: DraftUpdateRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[DraftService, Depends(draft_service)],
) -> TrainingDraftData:
    try:
        return service.update(
            user_id=user.id,
            draft_id=draft_id,
            data=request.model_dump(exclude_none=True),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DraftLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{draft_id}", status_code=204)
def delete_draft(
    draft_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[DraftService, Depends(draft_service)],
) -> None:
    try:
        service.delete(user_id=user.id, draft_id=draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

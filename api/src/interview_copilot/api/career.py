from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.agent.career_planner import CareerPlanningAgent
from interview_copilot.application.agent.skills import SkillRegistry, SkillRegistryError
from interview_copilot.application.agent.tools import ToolExecutor, ToolRegistry
from interview_copilot.application.career import CareerService
from interview_copilot.application.jobs import AiJobService
from interview_copilot.config import get_settings
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.career import (
    CareerProfile,
    CareerWorkspace,
    WeeklyPlan,
    WeeklyPlanDraft,
    WeeklyPlanItem,
)
from interview_copilot.domain.jobs import AiJobStatus
from interview_copilot.infrastructure.database import SessionFactory, get_database_session
from interview_copilot.infrastructure.jobs import AiJobRecord
from interview_copilot.providers.deepseek_agent import (
    DeepSeekAgentError,
    DeepSeekFunctionCallingClient,
)

router = APIRouter(prefix="/v1/career", tags=["career"])
settings = get_settings()


class CareerProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_role: str = Field(default="", max_length=150)
    target_level: str = Field(default="", max_length=50)
    target_companies: list[str] = Field(default_factory=list, max_length=20)
    preferred_cities: list[str] = Field(default_factory=list, max_length=20)
    weekly_hours: int = Field(default=5, ge=1, le=80)
    available_weekdays: list[int] = Field(
        default_factory=lambda: [0, 2, 4, 5], min_length=1, max_length=7
    )
    preferred_time_slot: Literal[
        "morning", "afternoon", "evening", "flexible"
    ] = "evening"
    constraints: str = Field(default="", max_length=2_000)


class WeeklyPlanDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date


class WeeklyPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date
    goal: str = Field(min_length=1, max_length=500)
    items: list[WeeklyPlanItem] = Field(min_length=1, max_length=20)
    status: Literal["active", "completed", "archived"] = "active"
    draft_id: UUID | None = None


class WeeklyPlanItemStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pending", "in_progress", "completed", "skipped"]


def career_planning_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> CareerService:
    return _career_planning_service(session)


def _career_planning_service(session: Session) -> CareerService:
    registry = ToolRegistry([])
    client = DeepSeekFunctionCallingClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        registry=registry,
        executor=ToolExecutor(registry),
        prompt_version="career-planning-agent-v1.2",
    )
    return CareerService(session, CareerPlanningAgent(SkillRegistry(), client))


@router.get("", response_model=CareerWorkspace)
def get_career_workspace(
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> CareerWorkspace:
    return CareerService(session).get(user_id=user.id)


@router.get("/today", response_model=list[WeeklyPlanItem])
def get_today_plan(
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
    target_date: Annotated[date | None, Query(alias="date")] = None,
) -> list[WeeklyPlanItem]:
    return CareerService(session).today(user_id=user.id, today=target_date)


@router.put("/profile", response_model=CareerProfile)
def save_career_profile(
    request: CareerProfileRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> CareerProfile:
    if any(day < 0 or day > 6 for day in request.available_weekdays):
        raise HTTPException(status_code=422, detail="可训练星期格式不正确")
    return CareerService(session).save_profile(
        user_id=user.id, profile=CareerProfile.model_validate(request.model_dump())
    )


@router.delete("/profile", status_code=204, response_class=Response)
def delete_career_profile(
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> Response:
    CareerService(session).delete_profile(user_id=user.id)
    return Response(status_code=204)


@router.post("/weekly-plan/draft", response_model=AiJobStatus, status_code=202)
async def generate_weekly_plan_draft(
    request: WeeklyPlanDraftRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> AiJobStatus:
    try:
        if request.week_start.weekday() != 0:
            raise ValueError("周计划开始日期必须是周一")
        job, created = AiJobService(session).create(
            user_id=user.id,
            kind="career_plan",
            stage="等待读取求职画像",
            estimated_seconds=60,
        )
        if created:
            background_tasks.add_task(
                _run_career_plan,
                job.id,
                user.id,
                request.week_start,
            )
        return job
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _run_career_plan(job_id: UUID, user_id: UUID, week_start: date) -> None:
    with SessionFactory() as session:
        if not session.get(AiJobRecord, job_id):
            return
        try:
            _update_career_job(job_id, stage="正在读取画像与训练证据", progress=10)

            def progress(stage: str, value: int) -> None:
                _update_career_job(job_id, stage=stage, progress=value)

            draft = await _career_planning_service(session).create_draft(
                user_id=user_id,
                request_id=job_id,
                week_start=week_start,
                progress=progress,
            )
            _complete_career_job(job_id, resource_id=draft.id)
        except (DeepSeekAgentError, SkillRegistryError, RuntimeError, ValueError) as exc:
            session.rollback()
            _fail_career_job(job_id, str(exc))


def _update_career_job(job_id: UUID, *, stage: str, progress: int) -> None:
    with SessionFactory() as job_session:
        record = job_session.get(AiJobRecord, job_id)
        if record:
            AiJobService(job_session).update(record, stage=stage, progress=progress)


def _complete_career_job(job_id: UUID, *, resource_id: UUID) -> None:
    with SessionFactory() as job_session:
        record = job_session.get(AiJobRecord, job_id)
        if record:
            AiJobService(job_session).complete(record, resource_id=resource_id)


def _fail_career_job(job_id: UUID, error: str) -> None:
    with SessionFactory() as job_session:
        record = job_session.get(AiJobRecord, job_id)
        if record:
            AiJobService(job_session).fail(record, error)


@router.get("/weekly-plan/draft/{draft_id}", response_model=WeeklyPlanDraft)
def get_weekly_plan_draft(
    draft_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> WeeklyPlanDraft:
    try:
        return CareerService(session).get_draft(user_id=user.id, draft_id=draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/weekly-plan", response_model=WeeklyPlan)
def save_weekly_plan(
    request: WeeklyPlanRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> WeeklyPlan:
    try:
        return CareerService(session).save_weekly_plan(
            user_id=user.id,
            week_start=request.week_start,
            goal=request.goal,
            items=request.items,
            status=request.status,
            draft_id=request.draft_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch(
    "/weekly-plan/{plan_id}/items/{item_id}", response_model=WeeklyPlanItem
)
def update_weekly_plan_item(
    plan_id: UUID,
    item_id: UUID,
    request: WeeklyPlanItemStatusRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> WeeklyPlanItem:
    try:
        return CareerService(session).update_item_status(
            user_id=user.id,
            plan_id=plan_id,
            item_id=item_id,
            status=request.status,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/weekly-plan/{plan_id}", status_code=204, response_class=Response)
def delete_weekly_plan(
    plan_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> Response:
    try:
        CareerService(session).delete_weekly_plan(user_id=user.id, plan_id=plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)

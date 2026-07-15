from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.ability_profile import AbilityProfileService
from interview_copilot.application.career import CareerService
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.career import (
    CareerProfile,
    CareerWorkspace,
    WeeklyPlan,
    WeeklyPlanItem,
)
from interview_copilot.infrastructure.database import get_database_session

router = APIRouter(prefix="/v1/career", tags=["career"])


class CareerProfileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_role: str = Field(default="", max_length=150)
    target_level: str = Field(default="", max_length=50)
    target_companies: list[str] = Field(default_factory=list, max_length=20)
    preferred_cities: list[str] = Field(default_factory=list, max_length=20)
    weekly_hours: int = Field(default=5, ge=1, le=80)
    constraints: str = Field(default="", max_length=2_000)


class WeeklyPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date
    goal: str = Field(min_length=1, max_length=500)
    items: list[WeeklyPlanItem] = Field(min_length=1, max_length=20)
    status: Literal["active", "completed", "archived"] = "active"


@router.get("", response_model=CareerWorkspace)
def get_career_workspace(
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> CareerWorkspace:
    ability = AbilityProfileService(session).get(user_id=user.id)
    focus = ability.coaching.next_focus or ability.next_training
    return CareerService(session).get(user_id=user.id, suggested_focus=focus)


@router.put("/profile", response_model=CareerProfile)
def save_career_profile(
    request: CareerProfileRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> CareerProfile:
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
        )
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

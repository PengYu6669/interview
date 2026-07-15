from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.ability_profile import AbilityProfileService
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.profile import AbilityProfileData
from interview_copilot.infrastructure.database import get_database_session

router = APIRouter(prefix="/v1/profile", tags=["profile"])


@router.get("", response_model=AbilityProfileData)
def get_ability_profile(
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> AbilityProfileData:
    return AbilityProfileService(session).get(user_id=user.id)

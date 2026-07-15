from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.boards import BoardConflictError, InterviewBoardService
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.board import BoardSnapshotData, BoardSnapshotRequest
from interview_copilot.infrastructure.database import get_database_session

router = APIRouter(prefix="/v1/interview-sessions", tags=["interview-boards"])


def board_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> InterviewBoardService:
    return InterviewBoardService(session)


@router.get("/{session_id}/board", response_model=BoardSnapshotData | None)
def get_interview_board(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewBoardService, Depends(board_service)],
) -> BoardSnapshotData | None:
    try:
        return service.get_latest(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/board", response_model=BoardSnapshotData)
def save_interview_board(
    session_id: UUID,
    request: BoardSnapshotRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewBoardService, Depends(board_service)],
) -> BoardSnapshotData:
    try:
        return service.save(user_id=user.id, session_id=session_id, request=request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BoardConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "current": exc.current.model_dump(mode="json")},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

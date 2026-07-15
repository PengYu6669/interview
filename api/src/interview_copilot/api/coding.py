from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.coding import CodingConflictError, InterviewCodingService
from interview_copilot.config import get_settings
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.coding import (
    CodingRunData,
    CodingRunRequest,
    CodingSnapshotRequest,
    CodingWorkspaceData,
)
from interview_copilot.infrastructure.database import get_database_session
from interview_copilot.sandbox.docker_python import (
    DockerPythonSandbox,
    DockerPythonSandboxConfig,
    SandboxUnavailableError,
)

router = APIRouter(prefix="/v1/interview-sessions", tags=["interview-coding"])
settings = get_settings()


def coding_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> InterviewCodingService:
    executor = None
    if settings.coding_sandbox_enabled:
        try:
            executor = DockerPythonSandbox(
                DockerPythonSandboxConfig(
                    image=settings.coding_sandbox_image,
                    timeout_seconds=settings.coding_sandbox_timeout_seconds,
                    memory_mb=settings.coding_sandbox_memory_mb,
                    cpu_count=settings.coding_sandbox_cpu_count,
                    pids_limit=settings.coding_sandbox_pids_limit,
                    output_limit_bytes=settings.coding_sandbox_output_limit_bytes,
                    max_concurrency=settings.coding_sandbox_max_concurrency,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return InterviewCodingService(session, executor)


@router.get("/{session_id}/coding", response_model=CodingWorkspaceData)
def get_coding_workspace(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewCodingService, Depends(coding_service)],
) -> CodingWorkspaceData:
    try:
        return service.get_workspace(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/coding", response_model=CodingWorkspaceData)
def save_coding_workspace(
    session_id: UUID,
    request: CodingSnapshotRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewCodingService, Depends(coding_service)],
) -> CodingWorkspaceData:
    try:
        return service.save(user_id=user.id, session_id=session_id, request=request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CodingConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "current": exc.current.model_dump(mode="json")},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/coding/runs", response_model=CodingRunData)
async def run_coding_workspace(
    session_id: UUID,
    request: CodingRunRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewCodingService, Depends(coding_service)],
) -> CodingRunData:
    try:
        return await service.run(user_id=user.id, session_id=session_id, request=request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CodingConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": str(exc), "current": exc.current.model_dump(mode="json")},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RuntimeError, SandboxUnavailableError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.claim_verification import (
    InterviewClaimVerificationService,
)
from interview_copilot.application.interview_reports import (
    InterviewReportError,
    InterviewReportInProgressError,
    InterviewReportReviewError,
    InterviewReportService,
)
from interview_copilot.application.retrieval.search import RagSearchService
from interview_copilot.config import get_settings
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.interviews import (
    InterviewHistoryItem,
    InterviewReportData,
    InterviewReportGenerationData,
    InterviewReportReviewData,
    InterviewReportReviewRequest,
)
from interview_copilot.infrastructure.database import get_database_session
from interview_copilot.infrastructure.rag_store import PostgresRagSearchRepository
from interview_copilot.providers.deepseek_claim_verification import (
    DeepSeekClaimVerificationProvider,
)
from interview_copilot.providers.deepseek_interview_report import (
    DeepSeekInterviewReportGenerator,
)
from interview_copilot.providers.deepseek_report_review import (
    DeepSeekInterviewReportReviewer,
)
from interview_copilot.providers.doubao_embedding import DoubaoEmbeddingProvider

router = APIRouter(prefix="/v1/interview-sessions", tags=["interview-reports"])
settings = get_settings()


def report_read_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> InterviewReportService:
    return InterviewReportService(session)


def report_write_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> InterviewReportService:
    try:
        generator = DeepSeekInterviewReportGenerator(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    embedding = DoubaoEmbeddingProvider(
        api_key=settings.doubao_embedding_api_key,
        endpoint=settings.doubao_embedding_endpoint,
        model=settings.doubao_embedding_model,
        dimensions=settings.doubao_embedding_dimensions,
    )
    verifier = InterviewClaimVerificationService(
        RagSearchService(PostgresRagSearchRepository(session), embedding),
        DeepSeekClaimVerificationProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        ),
    )
    return InterviewReportService(session, generator, verifier)


def report_reviewer() -> DeepSeekInterviewReportReviewer:
    try:
        return DeepSeekInterviewReportReviewer(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/history", response_model=list[InterviewHistoryItem])
def list_interview_history(
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewReportService, Depends(report_read_service)],
) -> list[InterviewHistoryItem]:
    return service.history(user_id=user.id)


@router.get("/{session_id}/report", response_model=InterviewReportData)
def get_interview_report(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewReportService, Depends(report_read_service)],
) -> InterviewReportData:
    try:
        return service.get(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{session_id}/report-status", response_model=InterviewReportGenerationData)
def get_interview_report_status(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewReportService, Depends(report_read_service)],
) -> InterviewReportGenerationData:
    try:
        return service.generation_status(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/report", response_model=InterviewReportData)
async def generate_interview_report(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewReportService, Depends(report_write_service)],
) -> InterviewReportData:
    try:
        return await service.generate(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InterviewReportInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InterviewReportError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{session_id}/report-reviews", response_model=InterviewReportReviewData)
async def review_interview_report_score(
    session_id: UUID,
    request: InterviewReportReviewRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewReportService, Depends(report_read_service)],
) -> InterviewReportReviewData:
    try:
        return await service.review(
            user_id=user.id,
            session_id=session_id,
            request=request,
            reviewer=report_reviewer() if request.action == "reevaluate" else None,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InterviewReportReviewError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_admin
from interview_copilot.application.question_workflows import QuestionWorkflowService
from interview_copilot.application.questions import QuestionBankAdminService
from interview_copilot.application.retrieval.indexing import RagIndexingService
from interview_copilot.config import get_settings
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.questions import AdminQuestionDetail, AdminQuestionSummary
from interview_copilot.infrastructure.database import get_database_session
from interview_copilot.infrastructure.rag_store import SqlAlchemyRagStore
from interview_copilot.providers.dashscope_embedding import DashScopeEmbeddingProvider

router = APIRouter(prefix="/v1/admin/questions", tags=["admin-questions"])
settings = get_settings()
ListItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
TopicName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class QuestionPublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    published: bool


class AdminQuestionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=250)
    prompt: str = Field(min_length=1, max_length=8_000)
    difficulty: Literal["基础", "进阶", "高级"]
    question_type: str = Field(min_length=1, max_length=30)
    framework: str = Field(min_length=1, max_length=30)
    intent: str = Field(min_length=1, max_length=4_000)
    answer_outline: list[ListItem] = Field(min_length=1, max_length=12)
    common_mistakes: list[ListItem] = Field(min_length=1, max_length=12)
    topic_names: list[TopicName] = Field(min_length=1, max_length=12)
    content_markdown: str = Field(default="", max_length=80_000)


def admin_question_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> QuestionBankAdminService:
    store = SqlAlchemyRagStore(session)
    indexer = QuestionWorkflowService(
        session,
        rag_indexing=RagIndexingService(
            store,
            DashScopeEmbeddingProvider(
                api_key=settings.dashscope_api_key,
                endpoint=settings.dashscope_embedding_endpoint,
                model=settings.dashscope_embedding_model,
                dimensions=settings.dashscope_embedding_dimensions,
            ),
        ),
    )
    return QuestionBankAdminService(session, indexer=indexer, visibility_store=store)


@router.get("", response_model=list[AdminQuestionSummary])
def list_admin_questions(
    admin: Annotated[UserProfile, Depends(require_admin)],
    service: Annotated[QuestionBankAdminService, Depends(admin_question_service)],
) -> list[AdminQuestionSummary]:
    del admin
    return service.list_managed()


@router.post("", response_model=AdminQuestionDetail, status_code=201)
async def create_admin_question(
    request: AdminQuestionUpdateRequest,
    admin: Annotated[UserProfile, Depends(require_admin)],
    service: Annotated[QuestionBankAdminService, Depends(admin_question_service)],
) -> AdminQuestionDetail:
    try:
        return await service.create_managed(admin_user_id=admin.id, **request.model_dump())
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{question_id}", response_model=AdminQuestionDetail)
def get_admin_question(
    question_id: UUID,
    admin: Annotated[UserProfile, Depends(require_admin)],
    service: Annotated[QuestionBankAdminService, Depends(admin_question_service)],
) -> AdminQuestionDetail:
    del admin
    try:
        return service.get_managed(question_id=question_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{question_id}", response_model=AdminQuestionDetail)
async def update_admin_question(
    question_id: UUID,
    request: AdminQuestionUpdateRequest,
    admin: Annotated[UserProfile, Depends(require_admin)],
    service: Annotated[QuestionBankAdminService, Depends(admin_question_service)],
) -> AdminQuestionDetail:
    del admin
    try:
        return await service.update_managed(
            question_id=question_id,
            **request.model_dump(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/{question_id}", status_code=204)
def delete_admin_question(
    question_id: UUID,
    admin: Annotated[UserProfile, Depends(require_admin)],
    service: Annotated[QuestionBankAdminService, Depends(admin_question_service)],
) -> None:
    del admin
    try:
        service.delete_managed(question_id=question_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{question_id}/publication", response_model=AdminQuestionSummary)
def set_question_publication(
    question_id: UUID,
    request: QuestionPublicationRequest,
    admin: Annotated[UserProfile, Depends(require_admin)],
    service: Annotated[QuestionBankAdminService, Depends(admin_question_service)],
) -> AdminQuestionSummary:
    try:
        return service.set_publication(
            admin_user_id=admin.id,
            question_id=question_id,
            published=request.published,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

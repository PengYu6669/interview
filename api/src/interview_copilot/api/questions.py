from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from interview_copilot.api.auth import optional_current_user, require_current_user
from interview_copilot.application.document_processing import process_document
from interview_copilot.application.question_workflows import QuestionWorkflowService
from interview_copilot.application.questions import QuestionBankService
from interview_copilot.application.retrieval.indexing import RagIndexingService
from interview_copilot.application.retrieval.search import RagSearchService
from interview_copilot.config import get_settings
from interview_copilot.document_parser import (
    InvalidDocumentError,
    ProtectedDocumentError,
    UnsupportedDocumentError,
)
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.questions import (
    QuestionChatAnswer,
    QuestionChatHistory,
    QuestionDetail,
    QuestionImportResult,
    QuestionSummary,
    UserQuestionState,
)
from interview_copilot.infrastructure.database import get_database_session
from interview_copilot.infrastructure.rag_store import (
    PostgresRagSearchRepository,
    SqlAlchemyRagStore,
)
from interview_copilot.providers.baidu_ocr import BaiduOCR, BaiduOCRConfig, BaiduOCRError
from interview_copilot.providers.deepseek_question_bank import DeepSeekQuestionBankProvider
from interview_copilot.providers.doubao_embedding import DoubaoEmbeddingProvider

router = APIRouter(prefix="/v1/questions", tags=["questions"])
settings = get_settings()
MAX_IMPORT_BYTES = 20 * 1024 * 1024


class UserQuestionStateRequest(BaseModel):
    status: Literal["unseen", "learning", "mastered", "review"]
    bookmarked: bool = False
    note: str = Field(default="", max_length=10_000)


class QuestionEditRequest(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    content_markdown: str = Field(min_length=1, max_length=80_000)


class QuestionChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)
    conversation_id: UUID | None = None


def service(session: Annotated[Session, Depends(get_database_session)]) -> QuestionBankService:
    return QuestionBankService(session)


def workflow_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> QuestionWorkflowService:
    embedding = DoubaoEmbeddingProvider(
        api_key=settings.doubao_embedding_api_key,
        endpoint=settings.doubao_embedding_endpoint,
        model=settings.doubao_embedding_model,
        dimensions=settings.doubao_embedding_dimensions,
    )
    return QuestionWorkflowService(
        session,
        deepseek=DeepSeekQuestionBankProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        ),
        rag_indexing=RagIndexingService(SqlAlchemyRagStore(session), embedding),
        rag_search=RagSearchService(PostgresRagSearchRepository(session), embedding),
    )


def workflow_read_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> QuestionWorkflowService:
    return QuestionWorkflowService(session)


@router.get("", response_model=list[QuestionSummary])
def list_questions(
    bank: Annotated[QuestionBankService, Depends(service)],
    topic: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
) -> list[QuestionSummary]:
    return bank.list_questions(topic=topic, difficulty=difficulty)


@router.get("/mine", response_model=list[QuestionSummary])
def list_my_questions(
    user: Annotated[UserProfile, Depends(require_current_user)],
    bank: Annotated[QuestionBankService, Depends(service)],
) -> list[QuestionSummary]:
    return bank.list_owned(user.id)


@router.get("/review-due", response_model=list[QuestionSummary])
def list_review_due(
    user: Annotated[UserProfile, Depends(require_current_user)],
    bank: Annotated[QuestionBankService, Depends(service)],
) -> list[QuestionSummary]:
    return bank.list_review_due(user_id=user.id)


@router.post("/import", response_model=QuestionImportResult, status_code=201)
async def import_questions(
    file: Annotated[UploadFile, File()],
    user: Annotated[UserProfile, Depends(require_current_user)],
    workflow: Annotated[QuestionWorkflowService, Depends(workflow_service)],
) -> QuestionImportResult:
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="文档不能超过 20MB")
    try:
        ocr = None
        if settings.baidu_ocr_access_token or (
            settings.baidu_ocr_api_key and settings.baidu_ocr_secret_key
        ):
            ocr = BaiduOCR(
                BaiduOCRConfig(
                    api_key=settings.baidu_ocr_api_key,
                    secret_key=settings.baidu_ocr_secret_key,
                    access_token=settings.baidu_ocr_access_token,
                )
            )
        try:
            processed = await process_document(
                filename=file.filename or "document",
                content=content,
                ocr=ocr,
            )
        finally:
            if ocr:
                await ocr.aclose()
        parsed = processed.document
        if not parsed.text.strip():
            raise InvalidDocumentError("文档没有可提取的文字")
        result = await workflow.import_document(
            user_id=user.id, filename=parsed.filename, text=parsed.text
        )
        result.warnings[:0] = processed.warnings
        return result
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except (ProtectedDocumentError, InvalidDocumentError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BaiduOCRError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{slug}", response_model=QuestionDetail)
def get_question(
    slug: str,
    bank: Annotated[QuestionBankService, Depends(service)],
    user: Annotated[UserProfile | None, Depends(optional_current_user)],
) -> QuestionDetail:
    try:
        return bank.get_question(slug, user_id=user.id if user else None)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{question_id}/content", status_code=204)
async def update_question_content(
    question_id: UUID,
    request: QuestionEditRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    workflow: Annotated[QuestionWorkflowService, Depends(workflow_service)],
) -> None:
    try:
        await workflow.update_owned(
            user_id=user.id, question_id=question_id, **request.model_dump()
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{question_id}/chat", response_model=QuestionChatAnswer)
async def chat_with_question(
    question_id: UUID,
    request: QuestionChatRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    workflow: Annotated[QuestionWorkflowService, Depends(workflow_service)],
) -> QuestionChatAnswer:
    try:
        return await workflow.chat(
            user_id=user.id,
            question_id=question_id,
            message=request.message,
            conversation_id=request.conversation_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{question_id}/chat", response_model=QuestionChatHistory | None)
def get_question_chat_history(
    question_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    workflow: Annotated[QuestionWorkflowService, Depends(workflow_read_service)],
) -> QuestionChatHistory | None:
    try:
        return workflow.get_chat_history(user_id=user.id, question_id=question_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{question_id}/state", response_model=UserQuestionState)
def get_state(
    question_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    bank: Annotated[QuestionBankService, Depends(service)],
) -> UserQuestionState:
    return bank.get_user_state(user_id=user.id, question_id=question_id)


@router.put("/{question_id}/state", response_model=UserQuestionState)
def update_state(
    question_id: UUID,
    request: UserQuestionStateRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    bank: Annotated[QuestionBankService, Depends(service)],
) -> UserQuestionState:
    try:
        return bank.update_state(user_id=user.id, question_id=question_id, **request.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

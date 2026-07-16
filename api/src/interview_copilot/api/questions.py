from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from interview_copilot.api.auth import optional_current_user, require_current_user
from interview_copilot.application.document_processing import process_document
from interview_copilot.application.jobs import AiJobService
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
from interview_copilot.domain.jobs import AiJobStatus
from interview_copilot.domain.questions import (
    QuestionChatAnswer,
    QuestionChatHistory,
    QuestionDetail,
    QuestionDocumentSummary,
    QuestionImportResult,
    QuestionSummary,
    UserQuestionState,
)
from interview_copilot.infrastructure.database import SessionFactory, get_database_session
from interview_copilot.infrastructure.jobs import AiJobRecord
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


def _workflow(session: Session) -> QuestionWorkflowService:
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


@router.post("/import", response_model=AiJobStatus, status_code=202)
async def import_questions(
    file: Annotated[UploadFile, File()],
    background_tasks: BackgroundTasks,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> AiJobStatus:
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="文档不能超过 20MB")
    estimated_seconds = min(240, 70 + max(0, len(content) // 200_000) * 15)
    job, created = AiJobService(session).create(
        user_id=user.id,
        kind="question_import",
        stage="等待解析资料",
        estimated_seconds=estimated_seconds,
    )
    if created:
        background_tasks.add_task(
            _run_question_import,
            job.id,
            user.id,
            file.filename or "document",
            file.content_type or "application/octet-stream",
            content,
        )
    return job


async def _run_question_import(
    job_id: UUID,
    user_id: UUID,
    filename: str,
    media_type: str,
    content: bytes,
) -> None:
    with SessionFactory() as session:
        if not session.get(AiJobRecord, job_id):
            return
        try:
            _update_job(job_id, stage="正在解析资料与识别文本", progress=8)
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
                    filename=filename,
                    content=content,
                    ocr=ocr,
                )
            finally:
                if ocr:
                    await ocr.aclose()
            parsed = processed.document
            if not parsed.text.strip():
                raise InvalidDocumentError("文档没有可提取的文字")

            def progress(stage: str, value: int, resource_id: UUID | None) -> None:
                _update_job(job_id, stage=stage, progress=value, resource_id=resource_id)

            result = await _workflow(session).import_document(
                user_id=user_id,
                filename=parsed.filename,
                media_type=parsed.media_type or media_type,
                text=parsed.text,
                initial_warnings=processed.warnings,
                progress=progress,
            )
            _complete_job(job_id, resource_id=result.document.id)
        except (
            UnsupportedDocumentError,
            ProtectedDocumentError,
            InvalidDocumentError,
            BaiduOCRError,
            RuntimeError,
            ValueError,
        ) as exc:
            session.rollback()
            _fail_job(job_id, str(exc))


def _update_job(
    job_id: UUID, *, stage: str, progress: int, resource_id: UUID | None = None
) -> None:
    with SessionFactory() as job_session:
        record = job_session.get(AiJobRecord, job_id)
        if record:
            AiJobService(job_session).update(
                record, stage=stage, progress=progress, resource_id=resource_id
            )


def _complete_job(job_id: UUID, *, resource_id: UUID) -> None:
    with SessionFactory() as job_session:
        record = job_session.get(AiJobRecord, job_id)
        if record:
            AiJobService(job_session).complete(record, resource_id=resource_id)


def _fail_job(job_id: UUID, error: str) -> None:
    with SessionFactory() as job_session:
        record = job_session.get(AiJobRecord, job_id)
        if record:
            AiJobService(job_session).fail(record, error)


@router.get("/documents", response_model=list[QuestionDocumentSummary])
def list_question_documents(
    user: Annotated[UserProfile, Depends(require_current_user)],
    workflow: Annotated[QuestionWorkflowService, Depends(workflow_read_service)],
) -> list[QuestionDocumentSummary]:
    return workflow.list_documents(user_id=user.id)


@router.post("/documents/{document_id}/regenerate", response_model=QuestionImportResult)
async def regenerate_question_document(
    document_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    workflow: Annotated[QuestionWorkflowService, Depends(workflow_service)],
) -> QuestionImportResult:
    try:
        return await workflow.regenerate_document(user_id=user.id, document_id=document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/documents/{document_id}", status_code=204)
def delete_question_document(
    document_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    workflow: Annotated[QuestionWorkflowService, Depends(workflow_read_service)],
) -> None:
    try:
        workflow.delete_document(user_id=user.id, document_id=document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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

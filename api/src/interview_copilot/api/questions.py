import asyncio
import logging
from contextlib import suppress
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from interview_copilot.api.auth import optional_current_user, require_current_user
from interview_copilot.application.document_processing import process_document
from interview_copilot.application.jobs import AiJobService
from interview_copilot.application.question_sets import QuestionSetService
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
    QuestionSetDetail,
    QuestionSetSummary,
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
from interview_copilot.providers.dashscope_embedding import DashScopeEmbeddingProvider
from interview_copilot.providers.qwen_question_bank import QwenQuestionBankProvider

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


class CreateQuestionSetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=250)
    question_ids: list[UUID] = Field(min_length=1, max_length=100)


def service(session: Annotated[Session, Depends(get_database_session)]) -> QuestionBankService:
    return QuestionBankService(session)


def workflow_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> QuestionWorkflowService:
    embedding = DashScopeEmbeddingProvider(
        api_key=settings.dashscope_api_key,
        endpoint=settings.dashscope_embedding_endpoint,
        model=settings.dashscope_embedding_model,
        dimensions=settings.dashscope_embedding_dimensions,
    )
    return QuestionWorkflowService(
        session,
        qwen=QwenQuestionBankProvider(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            model=settings.dashscope_model,
        ),
        rag_indexing=RagIndexingService(SqlAlchemyRagStore(session), embedding),
        rag_search=RagSearchService(PostgresRagSearchRepository(session), embedding),
    )


def _workflow(session: Session) -> QuestionWorkflowService:
    embedding = DashScopeEmbeddingProvider(
        api_key=settings.dashscope_api_key,
        endpoint=settings.dashscope_embedding_endpoint,
        model=settings.dashscope_embedding_model,
        dimensions=settings.dashscope_embedding_dimensions,
    )
    return QuestionWorkflowService(
        session,
        qwen=QwenQuestionBankProvider(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url,
            model=settings.dashscope_model,
        ),
        rag_indexing=RagIndexingService(SqlAlchemyRagStore(session), embedding),
        rag_search=RagSearchService(PostgresRagSearchRepository(session), embedding),
    )


def workflow_read_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> QuestionWorkflowService:
    return QuestionWorkflowService(session)


@router.get("/sets", response_model=list[QuestionSetSummary])
def list_question_sets(
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> list[QuestionSetSummary]:
    return QuestionSetService(session).list_owned(user_id=user.id)


@router.post("/sets", response_model=QuestionSetDetail, status_code=201)
def create_question_set(
    request: CreateQuestionSetRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> QuestionSetDetail:
    try:
        return QuestionSetService(session).create_custom(
            user_id=user.id,
            name=request.name,
            question_ids=request.question_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/sets/{question_set_id}", response_model=QuestionSetDetail)
def get_question_set(
    question_set_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> QuestionSetDetail:
    try:
        return QuestionSetService(session).get_owned(
            user_id=user.id, question_set_id=question_set_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
    question_limit: Annotated[int, Form(ge=10, le=100)] = 30,
) -> AiJobStatus:
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="文档不能超过 20MB")
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
            filename=file.filename or "document", content=content, ocr=ocr
        )
    finally:
        if ocr:
            await ocr.aclose()
    parsed = processed.document
    if not parsed.text.strip():
        raise HTTPException(status_code=422, detail="文档没有可提取的文字")
    # A 30-question import can require up to eight generation batches plus evidence repairs.
    estimated_seconds = 600 if question_limit <= 30 else 900
    job, created = AiJobService(session).create(
        user_id=user.id,
        kind="question_import",
        stage="等待解析资料",
        estimated_seconds=estimated_seconds,
        payload={
            "action": "import",
            "filename": parsed.filename,
            "media_type": parsed.media_type or file.content_type or "text/plain",
            "text": parsed.text,
            "warnings": processed.warnings,
            "question_limit": question_limit,
        },
    )
    del created
    return job


async def _run_question_import(
    job_id: UUID,
    user_id: UUID,
    filename: str,
    media_type: str,
    text: str,
    warnings: list[str],
    question_limit: int,
) -> None:
    with SessionFactory() as session:
        if not session.get(AiJobRecord, job_id):
            return
        try:
            _update_job(job_id, stage="正在建立资料索引", progress=8)

            def progress(stage: str, value: int, resource_id: UUID | None) -> None:
                _update_job(job_id, stage=stage, progress=value, resource_id=resource_id)

            result = await _workflow(session).import_document(
                user_id=user_id,
                filename=filename,
                media_type=media_type,
                text=text,
                initial_warnings=warnings,
                progress=progress,
                question_limit=question_limit,
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
            resource_id = record.resource_id
            AiJobService(job_session).fail(record, error)
            if resource_id:
                QuestionWorkflowService(job_session).recover_failed_document(
                    document_id=resource_id,
                    error=error,
                )


@router.get("/documents", response_model=list[QuestionDocumentSummary])
def list_question_documents(
    user: Annotated[UserProfile, Depends(require_current_user)],
    workflow: Annotated[QuestionWorkflowService, Depends(workflow_read_service)],
) -> list[QuestionDocumentSummary]:
    return workflow.list_documents(user_id=user.id)


@router.post("/documents/{document_id}/regenerate", response_model=AiJobStatus, status_code=202)
async def regenerate_question_document(
    document_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
    additional_limit: int = Query(default=30, ge=10, le=30),
) -> AiJobStatus:
    try:
        QuestionWorkflowService(session)._owned_document(user_id=user.id, document_id=document_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    job, created = AiJobService(session).create(
        user_id=user.id,
        kind="question_import",
        stage="等待补充未覆盖知识点",
        estimated_seconds=120,
        payload={
            "action": "regenerate",
            "document_id": str(document_id),
            "additional_limit": additional_limit,
        },
    )
    del created
    return job


# Hard wall-clock budget for one import/regenerate run (LLM + indexing).
_QUESTION_JOB_TIMEOUT_SECONDS = 20 * 60
logger = logging.getLogger(__name__)


async def run_question_job_worker(stop: asyncio.Event) -> None:
    while not stop.is_set():
        with SessionFactory() as session:
            # Sweep zombies even when the queue is empty so the UI stops spinning.
            AiJobService(session).expire_stale(kind="question_import")
            record = AiJobService(session).claim_next(kind="question_import")
            if record:
                payload = record.payload
                job_id = record.id
                user_id = record.user_id
                estimated = max(60, int(record.estimated_seconds or 240))
                timeout_seconds = min(
                    _QUESTION_JOB_TIMEOUT_SECONDS,
                    max(estimated * 3, 10 * 60),
                )
                AiJobService(session).release_worker_lease()
                try:
                    if payload.get("action") == "regenerate":
                        work = _run_question_regeneration(
                            job_id,
                            user_id,
                            UUID(payload["document_id"]),
                            int(payload["additional_limit"]),
                        )
                    else:
                        work = _run_question_import(
                            job_id,
                            user_id,
                            str(payload["filename"]),
                            str(payload["media_type"]),
                            str(payload["text"]),
                            list(payload.get("warnings", [])),
                            int(payload["question_limit"]),
                        )
                    await asyncio.wait_for(work, timeout=timeout_seconds)
                except TimeoutError:
                    _fail_job(
                        job_id,
                        "后台任务超时已自动停止，请缩小资料或降低题目数量后重试",
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    _fail_job(job_id, f"后台任务参数无效：{exc}")
                # Process boundary: keep one failed provider call from killing the worker.
                except Exception:
                    logger.exception("question import worker failed", extra={"job_id": str(job_id)})
                    _fail_job(job_id, "题目生成服务暂时不可用，请稍后重试")
                continue
        with suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=1)


async def _run_question_regeneration(
    job_id: UUID,
    user_id: UUID,
    document_id: UUID,
    additional_limit: int,
) -> None:
    with SessionFactory() as session:
        try:
            _update_job(job_id, stage="正在补充未覆盖知识点", progress=20)
            result = await _workflow(session).regenerate_document(
                user_id=user_id,
                document_id=document_id,
                additional_limit=additional_limit,
            )
            _complete_job(job_id, resource_id=result.document.id)
        except (LookupError, RuntimeError, ValueError) as exc:
            _fail_job(job_id, str(exc))


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

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.interview_planning import (
    InterviewPlanningError,
    InterviewPlanningService,
)
from interview_copilot.application.interview_runtime import (
    InterviewRuntimeService,
    InterviewTurnError,
)
from interview_copilot.application.retrieval.indexing import RagIndexingService
from interview_copilot.application.retrieval.search import RagSearchService
from interview_copilot.config import get_settings
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.interviews import InterviewRuntimeData, InterviewSessionData
from interview_copilot.infrastructure.database import SessionFactory, get_database_session
from interview_copilot.infrastructure.interviews import InterviewSessionRecord
from interview_copilot.infrastructure.rag_store import (
    PostgresRagSearchRepository,
    SqlAlchemyRagStore,
)
from interview_copilot.providers.deepseek_interview_planner import (
    DeepSeekInterviewPlanGenerator,
)
from interview_copilot.providers.deepseek_interview_turn import DeepSeekInterviewTurnDecider
from interview_copilot.providers.doubao_embedding import DoubaoEmbeddingProvider
from interview_copilot.speech.streaming import stream_xfyun_transcription
from interview_copilot.speech.tickets import (
    InvalidSpeechTicketError,
    SpeechTicketReplayGuard,
    SpeechTicketSigner,
    SpeechTicketStoreError,
)
from interview_copilot.speech.xfyun_iat import XfyunIATConfig

router = APIRouter(prefix="/v1/interview-sessions", tags=["interview-sessions"])
settings = get_settings()


class InterviewSessionCreateRequest(BaseModel):
    draft_id: UUID


class InterviewAnswerRequest(BaseModel):
    client_message_id: UUID
    answer: str = Field(min_length=1, max_length=20_000)
    answer_mode: str = Field(pattern="^(text|voice)$")


class InterviewInterruptionRequest(BaseModel):
    client_message_id: UUID
    partial_answer: str = Field(min_length=60, max_length=20_000)
    elapsed_seconds: int = Field(ge=12, le=55)


class InterviewInterruptionResponse(BaseModel):
    interrupted: bool
    runtime: InterviewRuntimeData


class SpeechTicketResponse(BaseModel):
    ticket: str
    expires_at: datetime


def planning_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> InterviewPlanningService:
    try:
        generator = DeepSeekInterviewPlanGenerator(
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
    return InterviewPlanningService(
        session,
        generator,
        rag_indexing=RagIndexingService(SqlAlchemyRagStore(session), embedding),
        rag_search=RagSearchService(PostgresRagSearchRepository(session), embedding),
    )


def session_read_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> InterviewPlanningService:
    return InterviewPlanningService(session)


def runtime_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> InterviewRuntimeService:
    try:
        decider = DeepSeekInterviewTurnDecider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return InterviewRuntimeService(session, decider)


@router.post("", response_model=InterviewSessionData, status_code=201)
async def create_interview_session(
    request: InterviewSessionCreateRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewPlanningService, Depends(planning_service)],
) -> InterviewSessionData:
    try:
        return await service.create(user_id=user.id, draft_id=request.draft_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InterviewPlanningError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=InterviewSessionData)
def get_interview_session(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewPlanningService, Depends(session_read_service)],
) -> InterviewSessionData:
    try:
        return service.get(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/start", response_model=InterviewRuntimeData)
def start_interview_session(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewPlanningService, Depends(session_read_service)],
) -> InterviewRuntimeData:
    try:
        return service.start(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{session_id}/runtime", response_model=InterviewRuntimeData)
def get_interview_runtime(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewPlanningService, Depends(session_read_service)],
) -> InterviewRuntimeData:
    try:
        return service.runtime(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/pause", response_model=InterviewRuntimeData)
def pause_interview_session(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewPlanningService, Depends(session_read_service)],
) -> InterviewRuntimeData:
    try:
        return service.pause(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/end", response_model=InterviewRuntimeData)
def end_interview_session(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewPlanningService, Depends(session_read_service)],
) -> InterviewRuntimeData:
    try:
        return service.end(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/answers", response_model=InterviewRuntimeData)
async def submit_interview_answer(
    session_id: UUID,
    request: InterviewAnswerRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewRuntimeService, Depends(runtime_service)],
) -> InterviewRuntimeData:
    try:
        return await service.answer(
            user_id=user.id,
            session_id=session_id,
            client_message_id=request.client_message_id,
            answer=request.answer,
            answer_mode=request.answer_mode,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InterviewTurnError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{session_id}/interruptions", response_model=InterviewInterruptionResponse)
async def assess_interview_interruption(
    session_id: UUID,
    request: InterviewInterruptionRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewRuntimeService, Depends(runtime_service)],
) -> InterviewInterruptionResponse:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        scope = service.interruption_scope(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        accepted = await redis.set(
            f"interview:interrupt:{user.id}:{session_id}:{scope}",
            "1",
            ex=75,
            nx=True,
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="实时打断保护服务暂时不可用") from exc
    finally:
        await redis.aclose()
    if not accepted:
        raise HTTPException(status_code=429, detail="本轮回答已经完成过实时打断判断")
    try:
        interrupted, runtime = await service.interrupt(
            user_id=user.id,
            session_id=session_id,
            client_message_id=request.client_message_id,
            partial_answer=request.partial_answer,
            elapsed_seconds=request.elapsed_seconds,
        )
        return InterviewInterruptionResponse(interrupted=interrupted, runtime=runtime)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InterviewTurnError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{session_id}/speech-ticket", response_model=SpeechTicketResponse)
def create_speech_ticket(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[InterviewPlanningService, Depends(session_read_service)],
) -> SpeechTicketResponse:
    runtime = service.runtime(user_id=user.id, session_id=session_id)
    if runtime.status != "started":
        raise HTTPException(status_code=409, detail="这场面试当前不能开始语音回答")
    try:
        ticket, expires_at = SpeechTicketSigner(settings.speech_ticket_secret).issue(
            user_id=user.id, session_id=session_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SpeechTicketResponse(ticket=ticket, expires_at=expires_at)


@router.websocket("/{session_id}/speech")
async def interview_speech_stream(
    websocket: WebSocket,
    session_id: UUID,
    ticket: str = Query(min_length=20, max_length=2_000),
) -> None:
    origin = websocket.headers.get("origin")
    if origin != settings.web_origin:
        await websocket.close(code=4403, reason="请求来源不受信任")
        return
    try:
        ticket_data = SpeechTicketSigner(settings.speech_ticket_secret).verify(ticket)
    except ValueError:
        await websocket.close(code=4401, reason="语音票据无效或已过期")
        return
    if ticket_data.session_id != session_id:
        await websocket.close(code=4403, reason="语音票据与面试会话不匹配")
        return
    with SessionFactory() as session:
        record = session.get(InterviewSessionRecord, session_id)
        if not record or record.user_id != ticket_data.user_id or record.status != "started":
            await websocket.close(code=4404, reason="找不到可用的面试会话")
            return
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await SpeechTicketReplayGuard(redis).consume(ticket_data)
    except InvalidSpeechTicketError:
        await websocket.close(code=4401, reason="语音票据已使用")
        return
    except SpeechTicketStoreError:
        await websocket.close(code=1013, reason="语音票据服务暂时不可用")
        return
    finally:
        await redis.aclose()
    await stream_xfyun_transcription(
        websocket,
        config=XfyunIATConfig(
            app_id=settings.iflytek_tts_app_id,
            api_key=settings.iflytek_tts_api_key,
            api_secret=settings.iflytek_tts_api_secret,
            endpoint=settings.iflytek_iat_endpoint,
        ),
    )

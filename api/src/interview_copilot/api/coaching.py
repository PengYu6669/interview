from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from interview_copilot.api.auth import require_current_user
from interview_copilot.application.agent.coach import TrainingCoachAgent
from interview_copilot.application.agent.skills import SkillRegistry, SkillRegistryError
from interview_copilot.application.agent.tools import (
    ToolExecutor,
    build_retrieval_tool_registry,
)
from interview_copilot.application.coaching import CoachingService
from interview_copilot.application.retrieval.search import RagSearchService
from interview_copilot.config import get_settings
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.coaching import (
    CoachingChannel,
    CoachingDifficulty,
    CoachingExerciseType,
    CoachingMode,
    CoachingSessionData,
    CoachingSessionSummary,
)
from interview_copilot.infrastructure.agent_audit import SqlAlchemyToolAuditSink
from interview_copilot.infrastructure.coaching import CoachingSessionRecord
from interview_copilot.infrastructure.database import SessionFactory, get_database_session
from interview_copilot.infrastructure.rag_store import PostgresRagSearchRepository
from interview_copilot.providers.deepseek_agent import (
    DeepSeekAgentError,
    DeepSeekFunctionCallingClient,
)
from interview_copilot.providers.doubao_embedding import DoubaoEmbeddingProvider
from interview_copilot.speech.streaming import stream_xfyun_transcription
from interview_copilot.speech.tickets import (
    InvalidSpeechTicketError,
    SpeechTicketReplayGuard,
    SpeechTicketSigner,
    SpeechTicketStoreError,
)
from interview_copilot.speech.xfyun_iat import XfyunIATConfig

router = APIRouter(prefix="/v1/coaching-sessions", tags=["coaching-sessions"])
settings = get_settings()


class CoachingCreateRequest(BaseModel):
    mode: CoachingMode
    channel: CoachingChannel
    target_role: str = Field(min_length=1, max_length=150)
    training_goal: str = Field(default="", max_length=500)
    source_ids: list[UUID] = Field(default_factory=list, max_length=30)
    exercise_type: CoachingExerciseType | None = None
    difficulty: CoachingDifficulty = "guided"


class CoachingAnswerRequest(BaseModel):
    client_message_id: UUID
    answer: str = Field(min_length=1, max_length=20_000)
    answer_mode: CoachingChannel
    elapsed_seconds: int | None = Field(default=None, ge=0, le=3_600)


class CoachingSpeechTicketResponse(BaseModel):
    ticket: str
    expires_at: datetime


def coaching_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> CoachingService:
    embedding = DoubaoEmbeddingProvider(
        api_key=settings.doubao_embedding_api_key,
        endpoint=settings.doubao_embedding_endpoint,
        model=settings.doubao_embedding_model,
        dimensions=settings.doubao_embedding_dimensions,
    )
    search = RagSearchService(PostgresRagSearchRepository(session), embedding)
    registry = build_retrieval_tool_registry(search)
    executor = ToolExecutor(registry, audit_sink=SqlAlchemyToolAuditSink())
    client = DeepSeekFunctionCallingClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        registry=registry,
        executor=executor,
    )
    return CoachingService(session, TrainingCoachAgent(SkillRegistry(), client))


def coaching_read_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> CoachingService:
    return CoachingService(session)


@router.get("", response_model=list[CoachingSessionSummary])
def list_coaching_sessions(
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[CoachingService, Depends(coaching_read_service)],
    limit: int = 5,
) -> list[CoachingSessionSummary]:
    try:
        return service.list_recent(user_id=user.id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=CoachingSessionData, status_code=201)
async def create_coaching_session(
    request: CoachingCreateRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[CoachingService, Depends(coaching_service)],
) -> CoachingSessionData:
    try:
        return await service.create(user_id=user.id, request_id=uuid4(), **request.model_dump())
    except (DeepSeekAgentError, SkillRegistryError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=CoachingSessionData)
def get_coaching_session(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[CoachingService, Depends(coaching_read_service)],
) -> CoachingSessionData:
    try:
        return service.get(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{session_id}/start", response_model=CoachingSessionData)
def start_coaching_session(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[CoachingService, Depends(coaching_read_service)],
) -> CoachingSessionData:
    try:
        return service.start(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{session_id}/answers", response_model=CoachingSessionData)
async def answer_coaching_session(
    session_id: UUID,
    request: CoachingAnswerRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[CoachingService, Depends(coaching_service)],
) -> CoachingSessionData:
    try:
        return await service.answer(user_id=user.id, session_id=session_id, **request.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (DeepSeekAgentError, SkillRegistryError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{session_id}/speech-ticket", response_model=CoachingSpeechTicketResponse)
def create_coaching_speech_ticket(
    session_id: UUID,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[CoachingService, Depends(coaching_read_service)],
) -> CoachingSpeechTicketResponse:
    try:
        session = service.get(user_id=user.id, session_id=session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if session.status != "active":
        raise HTTPException(status_code=409, detail="这项训练当前不能开始语音回答")
    try:
        ticket, expires_at = SpeechTicketSigner(settings.speech_ticket_secret).issue(
            user_id=user.id, session_id=session_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return CoachingSpeechTicketResponse(ticket=ticket, expires_at=expires_at)


@router.websocket("/{session_id}/speech")
async def coaching_speech_stream(
    websocket: WebSocket,
    session_id: UUID,
    ticket: str = Query(min_length=20, max_length=2_000),
) -> None:
    if websocket.headers.get("origin") != settings.web_origin:
        await websocket.close(code=4403, reason="请求来源不受信任")
        return
    try:
        ticket_data = SpeechTicketSigner(settings.speech_ticket_secret).verify(ticket)
    except ValueError:
        await websocket.close(code=4401, reason="语音票据无效或已过期")
        return
    if ticket_data.session_id != session_id:
        await websocket.close(code=4403, reason="语音票据与训练会话不匹配")
        return
    with SessionFactory() as session:
        record = session.get(CoachingSessionRecord, session_id)
        if not record or record.user_id != ticket_data.user_id or record.status != "active":
            await websocket.close(code=4404, reason="找不到可用的专项训练")
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

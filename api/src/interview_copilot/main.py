from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .api.auth import require_current_user
from .api.auth import router as auth_router
from .api.boards import router as boards_router
from .api.career import router as career_router
from .api.coaching import router as coaching_router
from .api.coding import router as coding_router
from .api.drafts import router as drafts_router
from .api.interviews import router as interviews_router
from .api.profile import router as profile_router
from .api.questions import router as questions_router
from .api.reports import router as reports_router
from .application.document_processing import process_document
from .application.resume_extraction import ExtractResumeProfile, ResumeExtractionError
from .config import get_settings
from .document_parser import (
    InvalidDocumentError,
    ProtectedDocumentError,
    UnsupportedDocumentError,
)
from .domain.auth import UserProfile
from .domain.resume import ResumeExtractionResult
from .infrastructure.database import engine
from .infrastructure.request_observability import (
    RequestObservabilityMiddleware,
    http_exception_response,
    unexpected_exception_response,
    validation_exception_response,
)
from .providers.baidu_ocr import BaiduOCR, BaiduOCRConfig, BaiduOCRError
from .providers.deepseek import DeepSeekResumeExtractor
from .tts.xfyun import XfyunTTS, XfyunTTSConfig, XfyunTTSError

settings = get_settings()
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(auth_router)
app.include_router(boards_router)
app.include_router(coaching_router)
app.include_router(coding_router)
app.include_router(career_router)
app.include_router(drafts_router)
app.include_router(reports_router)
app.include_router(interviews_router)
app.include_router(profile_router)
app.include_router(questions_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestObservabilityMiddleware)
app.add_exception_handler(HTTPException, http_exception_response)
app.add_exception_handler(RequestValidationError, validation_exception_response)
app.add_exception_handler(Exception, unexpected_exception_response)


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class ParsedDocumentResponse(BaseModel):
    filename: str
    media_type: str
    text: str
    page_count: int | None
    warnings: list[str]


class ResumeExtractionRequest(BaseModel):
    resume_text: str = Field(min_length=1, max_length=80_000)
    jd: str = Field(default="", max_length=30_000)
    target_role: str = Field(min_length=1, max_length=150)


async def get_resume_extraction_use_case() -> AsyncIterator[ExtractResumeProfile]:
    try:
        provider = DeepSeekResumeExtractor(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        yield ExtractResumeProfile(provider, model_name=settings.deepseek_model)
    finally:
        await provider.aclose()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def readiness() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        redis = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        try:
            redis.ping()
        finally:
            redis.close()
    except (SQLAlchemyError, RedisError, OSError) as exc:
        raise HTTPException(status_code=503, detail="依赖服务尚未就绪") from exc
    return {"status": "ready"}


@app.post("/v1/documents/parse", response_model=ParsedDocumentResponse)
async def parse_uploaded_document(
    file: Annotated[UploadFile, File()],
) -> ParsedDocumentResponse:
    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
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
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ProtectedDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BaiduOCRError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    parsed = processed.document
    return ParsedDocumentResponse(
        filename=parsed.filename,
        media_type=parsed.media_type,
        text=parsed.text,
        page_count=parsed.page_count,
        warnings=processed.warnings,
    )


@app.post("/v1/tts/xfyun", response_class=Response)
async def synthesize_speech(
    request: TTSRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
) -> Response:
    del user
    provider = XfyunTTS(
        XfyunTTSConfig(
            app_id=settings.iflytek_tts_app_id,
            api_key=settings.iflytek_tts_api_key,
            api_secret=settings.iflytek_tts_api_secret,
            endpoint=settings.iflytek_tts_endpoint,
            voice=settings.iflytek_tts_voice,
        )
    )
    try:
        audio = await provider.synthesize(request.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except XfyunTTSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/v1/resumes/extract", response_model=ResumeExtractionResult)
async def extract_resume_profile(
    request: ResumeExtractionRequest,
    use_case: Annotated[ExtractResumeProfile, Depends(get_resume_extraction_use_case)],
) -> ResumeExtractionResult:
    try:
        return await use_case.execute(
            resume_text=request.resume_text,
            jd=request.jd,
            target_role=request.target_role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ResumeExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_API_DIR = Path(__file__).resolve().parents[2]
_REPOSITORY_ROOT = _API_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPOSITORY_ROOT / ".env", _API_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "InterviewCopilot API"
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://interview:interview_dev@localhost:5432/interview_copilot"
    )
    redis_url: str = "redis://localhost:6379/0"
    web_origin: str = "http://localhost:3000"
    auth_session_days: int = 7
    auth_login_max_failures: int = Field(default=8, ge=3, le=100)
    auth_login_window_seconds: int = Field(default=900, ge=60, le=86_400)

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_anthropic_base_url: str = "https://api.deepseek.com/anthropic"
    deepseek_model: str = "deepseek-v4-flash"

    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_model: str = "doubao-seed-2-1-pro-260628"

    doubao_embedding_api_key: str = ""
    doubao_embedding_endpoint: str = (
        "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"
    )
    doubao_embedding_model: str = ""
    doubao_embedding_dimensions: int = 1024

    baidu_ocr_bearer_token: str = ""
    baidu_ocr_access_token: str = ""
    baidu_ocr_api_key: str = ""
    baidu_ocr_secret_key: str = ""

    iflytek_tts_app_id: str = ""
    iflytek_tts_api_key: str = ""
    iflytek_tts_api_secret: str = ""
    iflytek_tts_endpoint: str = "wss://tts-api.xfyun.cn/v2/tts"
    iflytek_tts_voice: str = "xiaoyan"
    iflytek_iat_endpoint: str = "wss://iat-api.xfyun.cn/v2/iat"
    speech_ticket_secret: str = ""

    coding_sandbox_enabled: bool = True
    coding_sandbox_image: str = (
        "python:3.12.11-alpine3.22@sha256:"
        "efcdfa6a6b2fd2afb9c7dfa9a5b288a6f68338b5cfdebe6b637d986067d85757"
    )
    coding_sandbox_timeout_seconds: float = Field(default=3.0, ge=1.0, le=10.0)
    coding_sandbox_memory_mb: int = Field(default=128, ge=64, le=256)
    coding_sandbox_cpu_count: float = Field(default=0.5, ge=0.25, le=1.0)
    coding_sandbox_pids_limit: int = Field(default=64, ge=16, le=128)
    coding_sandbox_output_limit_bytes: int = Field(default=65_536, ge=8_192, le=131_072)
    coding_sandbox_max_concurrency: int = Field(default=2, ge=1, le=4)


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()

import asyncio
import base64
import time
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

ACCURATE_BASIC_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
OAUTH_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
MAX_OCR_PDF_BYTES = 10 * 1024 * 1024
MAX_OCR_PAGES = 20


class BaiduOCRError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BaiduOCRConfig:
    api_key: str
    secret_key: str
    access_token: str = ""


class OAuthTokenResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    access_token: str = Field(min_length=1)
    expires_in: int = Field(gt=0)


class OCRWord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    words: str


class OCRResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    words_result: list[OCRWord] = Field(default_factory=list)
    error_code: int | None = None
    error_msg: str | None = None


class BaiduOCR:
    def __init__(
        self,
        config: BaiduOCRConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not config.access_token and not (config.api_key and config.secret_key):
            raise ValueError("百度 OCR 需要 access_token 或 API Key + Secret Key")
        self._config = config
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30, connect=10),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )
        self._owns_client = client is None
        self._cached_token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    async def recognize_pdf(self, content: bytes, *, page_count: int) -> str:
        if not content.startswith(b"%PDF-"):
            raise ValueError("OCR 输入不是有效的 PDF")
        if len(content) > MAX_OCR_PDF_BYTES:
            raise ValueError("扫描版 PDF 不能超过 10MB")
        if page_count < 1 or page_count > MAX_OCR_PAGES:
            raise ValueError(f"扫描版 PDF 页数必须为 1 至 {MAX_OCR_PAGES} 页")
        token = await self._access_token()
        encoded = base64.b64encode(content).decode("ascii")
        pages = []
        for page_number in range(1, page_count + 1):
            response = await self._recognize_page(
                token=token,
                pdf_base64=encoded,
                page_number=page_number,
            )
            text = "\n".join(
                word.words.strip() for word in response.words_result if word.words.strip()
            )
            if text:
                pages.append(text)
        if not pages:
            raise BaiduOCRError("百度 OCR 没有识别到可用文字")
        return "\n\n".join(pages)

    async def _recognize_page(
        self,
        *,
        token: str,
        pdf_base64: str,
        page_number: int,
    ) -> OCRResponse:
        try:
            response = await self._client.post(
                ACCURATE_BASIC_URL,
                params={"access_token": token},
                headers={"Accept": "application/json"},
                data={
                    "pdf_file": pdf_base64,
                    "pdf_file_num": str(page_number),
                    "detect_direction": "false",
                    "probability": "false",
                },
            )
            response.raise_for_status()
            payload = OCRResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise BaiduOCRError(f"百度 OCR 第 {page_number} 页识别失败") from exc
        if payload.error_code not in (None, 0):
            message = payload.error_msg or "未知厂商错误"
            raise BaiduOCRError(
                f"百度 OCR 第 {page_number} 页识别失败：{message}（{payload.error_code}）"
            )
        return payload

    async def _access_token(self) -> str:
        if self._config.access_token:
            return self._config.access_token
        now = time.monotonic()
        if self._cached_token and self._token_expires_at > now + 60:
            return self._cached_token
        async with self._token_lock:
            now = time.monotonic()
            if self._cached_token and self._token_expires_at > now + 60:
                return self._cached_token
            try:
                response = await self._client.post(
                    OAUTH_TOKEN_URL,
                    params={
                        "grant_type": "client_credentials",
                        "client_id": self._config.api_key,
                        "client_secret": self._config.secret_key,
                    },
                )
                response.raise_for_status()
                payload = OAuthTokenResponse.model_validate(response.json())
            except (httpx.HTTPError, ValueError, ValidationError) as exc:
                raise BaiduOCRError("百度 OCR 鉴权失败") from exc
            self._cached_token = payload.access_token
            self._token_expires_at = now + payload.expires_in
            return payload.access_token

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

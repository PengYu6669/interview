import asyncio
import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime
from urllib.parse import urlencode, urlparse

import websockets


class XfyunTTSError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class XfyunTTSConfig:
    app_id: str
    api_key: str
    api_secret: str
    endpoint: str
    voice: str = "xiaoyan"


class XfyunTTS:
    def __init__(self, config: XfyunTTSConfig) -> None:
        self.config = config

    async def synthesize(self, text: str) -> bytes:
        if not all((self.config.app_id, self.config.api_key, self.config.api_secret)):
            raise XfyunTTSError("尚未配置科大讯飞 TTS 凭据")
        encoded = text.encode("utf-8")
        if not encoded or len(encoded) >= 8_000:
            raise ValueError("单次语音合成文本必须为 1 至 7999 个 UTF-8 字节")
        url = self._authenticated_url()
        request = {
            "common": {"app_id": self.config.app_id},
            "business": {
                "aue": "lame",
                "sfl": 1,
                "auf": "audio/L16;rate=16000",
                "vcn": self.config.voice,
                "tte": "UTF8",
                "speed": 44,
                "volume": 58,
                "pitch": 48,
            },
            "data": {
                "status": 2,
                "text": base64.b64encode(encoded).decode("ascii"),
            },
        }
        chunks: list[bytes] = []
        try:
            async with websockets.connect(
                url, open_timeout=10, close_timeout=5, max_size=4 * 1024 * 1024
            ) as websocket:
                await websocket.send(json.dumps(request, ensure_ascii=False))
                async with asyncio.timeout(30):
                    async for raw in websocket:
                        payload = json.loads(raw)
                        code = payload.get("code")
                        if code != 0:
                            raise XfyunTTSError(
                                f"科大讯飞语音合成失败：{payload.get('message', '未知错误')}"
                            )
                        data = payload.get("data") or {}
                        audio = data.get("audio")
                        if audio:
                            chunks.append(base64.b64decode(audio, validate=True))
                        if data.get("status") == 2:
                            break
        except XfyunTTSError:
            raise
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise XfyunTTSError("科大讯飞语音合成连接失败") from exc
        if not chunks:
            raise XfyunTTSError("科大讯飞没有返回音频数据")
        return b"".join(chunks)

    def _authenticated_url(self) -> str:
        parsed = urlparse(self.config.endpoint)
        if parsed.scheme != "wss" or not parsed.hostname or not parsed.path:
            raise ValueError("科大讯飞 TTS endpoint 必须是有效的 wss 地址")
        date = format_datetime(datetime.now(UTC), usegmt=True)
        signature_origin = f"host: {parsed.hostname}\ndate: {date}\nGET {parsed.path} HTTP/1.1"
        digest = hmac.new(
            self.config.api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(digest).decode("ascii")
        authorization_origin = (
            f'api_key="{self.config.api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("ascii")
        query = urlencode({"authorization": authorization, "date": date, "host": parsed.hostname})
        return f"{self.config.endpoint}?{query}"

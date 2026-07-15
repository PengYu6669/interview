import asyncio
import base64
import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime
from urllib.parse import urlencode, urlparse

import websockets
from websockets.asyncio.client import ClientConnection


class XfyunIATError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class XfyunIATConfig:
    app_id: str
    api_key: str
    api_secret: str
    endpoint: str


class XfyunIAT:
    def __init__(self, config: XfyunIATConfig) -> None:
        self.config = config

    async def transcribe(self, audio: AsyncIterator[bytes]) -> AsyncIterator[str]:
        if not all((self.config.app_id, self.config.api_key, self.config.api_secret)):
            raise XfyunIATError("尚未配置科大讯飞 IAT 凭据")
        transcripts: dict[int, str] = {}
        try:
            async with websockets.connect(
                self._authenticated_url(),
                open_timeout=10,
                close_timeout=5,
                max_size=2 * 1024 * 1024,
            ) as websocket:
                producer = asyncio.create_task(self._send_audio(websocket, audio))
                try:
                    async with asyncio.timeout(70):
                        async for raw in websocket:
                            payload = json.loads(raw)
                            if payload.get("code") != 0:
                                raise XfyunIATError(
                                    f"科大讯飞语音听写失败：{payload.get('message', '未知错误')}"
                                )
                            data = payload.get("data") or {}
                            result = data.get("result") or {}
                            self._merge_result(transcripts, result)
                            yield "".join(transcripts[index] for index in sorted(transcripts))
                            if data.get("status") == 2:
                                break
                finally:
                    if not producer.done():
                        producer.cancel()
                    await asyncio.gather(producer, return_exceptions=True)
        except XfyunIATError:
            raise
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            raise XfyunIATError("科大讯飞语音听写连接失败") from exc

    async def _send_audio(
        self, websocket: ClientConnection, audio: AsyncIterator[bytes]
    ) -> None:
        first = True
        sent_audio = False
        async for chunk in audio:
            if not chunk:
                continue
            sent_audio = True
            frame: dict[str, object] = {
                "data": {
                    "status": 0 if first else 1,
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": base64.b64encode(chunk).decode("ascii"),
                }
            }
            if first:
                frame["common"] = {"app_id": self.config.app_id}
                frame["business"] = {
                    "language": "zh_cn",
                    "domain": "iat",
                    "accent": "mandarin",
                    "dwa": "wpgs",
                    "vad_eos": 3_000,
                }
                first = False
            await websocket.send(json.dumps(frame, ensure_ascii=False))
        if not sent_audio:
            raise XfyunIATError("没有收到可识别的音频")
        await websocket.send(
            json.dumps(
                {
                    "data": {
                        "status": 2,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": "",
                    }
                }
            )
        )

    @staticmethod
    def _merge_result(transcripts: dict[int, str], result: dict) -> None:
        sequence = int(result.get("sn", len(transcripts)))
        if result.get("pgs") == "rpl":
            replace_range = result.get("rg") or []
            if len(replace_range) == 2:
                for index in range(int(replace_range[0]), int(replace_range[1]) + 1):
                    transcripts.pop(index, None)
        words = "".join(
            str(candidate.get("w", ""))
            for group in result.get("ws", [])
            for candidate in (group.get("cw") or [])[:1]
        )
        transcripts[sequence] = words

    def _authenticated_url(self) -> str:
        parsed = urlparse(self.config.endpoint)
        if parsed.scheme != "wss" or not parsed.hostname or not parsed.path:
            raise ValueError("科大讯飞 IAT endpoint 必须是有效的 wss 地址")
        date = format_datetime(datetime.now(UTC), usegmt=True)
        origin = f"host: {parsed.hostname}\ndate: {date}\nGET {parsed.path} HTTP/1.1"
        digest = hmac.new(
            self.config.api_secret.encode(), origin.encode(), hashlib.sha256
        ).digest()
        signature = base64.b64encode(digest).decode()
        authorization = base64.b64encode(
            (
                f'api_key="{self.config.api_key}", algorithm="hmac-sha256", '
                f'headers="host date request-line", signature="{signature}"'
            ).encode()
        ).decode()
        query = urlencode(
            {"authorization": authorization, "date": date, "host": parsed.hostname}
        )
        return f"{self.config.endpoint}?{query}"

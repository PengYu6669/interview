from collections.abc import AsyncIterator

from fastapi import WebSocket, WebSocketDisconnect

from .xfyun_iat import XfyunIAT, XfyunIATConfig, XfyunIATError


async def stream_xfyun_transcription(
    websocket: WebSocket,
    *,
    config: XfyunIATConfig,
) -> None:
    await websocket.accept()
    provider = XfyunIAT(config)

    async def audio_stream() -> AsyncIterator[bytes]:
        total = 0
        while True:
            chunk = await websocket.receive_bytes()
            if not chunk:
                break
            total += len(chunk)
            if len(chunk) > 9_600 or total > 2_000_000:
                raise ValueError("语音数据超过单次听写限制")
            yield chunk

    try:
        async for transcript in provider.transcribe(audio_stream()):
            await websocket.send_json({"type": "transcript", "text": transcript})
        await websocket.send_json({"type": "completed"})
        await websocket.close(code=1000)
    except WebSocketDisconnect:
        return
    except (XfyunIATError, ValueError) as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
        await websocket.close(code=1011)


import base64
from urllib.parse import parse_qs, urlparse

import pytest

from interview_copilot.tts.xfyun import XfyunTTS, XfyunTTSConfig


def test_builds_signed_wss_url_without_exposing_secret() -> None:
    provider = XfyunTTS(
        XfyunTTSConfig(
            app_id="app",
            api_key="key",
            api_secret="secret",
            endpoint="wss://tts-api.xfyun.cn/v2/tts",
        )
    )

    url = provider._authenticated_url()
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    authorization = base64.b64decode(query["authorization"][0]).decode("utf-8")

    assert parsed.scheme == "wss"
    assert query["host"] == ["tts-api.xfyun.cn"]
    assert 'api_key="key"' in authorization
    assert "secret" not in url


@pytest.mark.asyncio
async def test_rejects_empty_and_oversized_text_before_connecting() -> None:
    provider = XfyunTTS(
        XfyunTTSConfig(
            app_id="app",
            api_key="key",
            api_secret="secret",
            endpoint="wss://tts-api.xfyun.cn/v2/tts",
        )
    )

    with pytest.raises(ValueError, match="1 至 7999"):
        await provider.synthesize("")
    with pytest.raises(ValueError, match="1 至 7999"):
        await provider.synthesize("中" * 3_000)

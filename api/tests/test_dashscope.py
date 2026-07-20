import json

import httpx
import pytest

from interview_copilot.providers.dashscope import (
    DashScopeChatClient,
    DashScopeEmbeddingProvider,
    DashScopeError,
)


@pytest.mark.asyncio
async def test_chat_request_disables_thinking_and_enables_json_mode() -> None:
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "{}"}}]},
        )

    client = DashScopeChatClient(
        api_key="test-key",
        base_url="https://example.invalid/v1",
        model="qwen3.7-plus",
    )
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://example.invalid/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        message = await client.complete(
            messages=[{"role": "user", "content": "返回 JSON"}],
            max_tokens=256,
        )
    finally:
        await client.aclose()

    assert message["content"] == "{}"
    assert requests == [
        {
            "model": "qwen3.7-plus",
            "messages": [{"role": "user", "content": "返回 JSON"}],
            "temperature": 0,
            "max_tokens": 256,
            "enable_thinking": False,
            "response_format": {"type": "json_object"},
        }
    ]


@pytest.mark.asyncio
async def test_chat_normalizes_vendor_failure() -> None:
    client = DashScopeChatClient(
        api_key="test-key",
        base_url="https://example.invalid/v1",
        model="qwen3.7-plus",
    )
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="https://example.invalid/v1",
        transport=httpx.MockTransport(lambda _: httpx.Response(500)),
    )
    try:
        with pytest.raises(DashScopeError, match="阿里云模型请求失败"):
            await client.complete(
                messages=[{"role": "user", "content": "测试"}],
                max_tokens=32,
            )
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_embedding_uses_dashscope_contract_and_validates_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient

    def fake_client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake_client)
    provider = DashScopeEmbeddingProvider(
        api_key="test-key",
        endpoint="https://example.invalid/v1/embeddings",
        model="text-embedding-v4",
        dimensions=3,
    )

    assert await provider.embed("面试准备") == [0.1, 0.2, 0.3]
    assert requests == [
        {
            "model": "text-embedding-v4",
            "input": "面试准备",
            "dimensions": 3,
            "encoding_format": "float",
        }
    ]


@pytest.mark.asyncio
async def test_embedding_rejects_unexpected_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, json={"data": [{"embedding": [0.1]}]})
    )
    original_client = httpx.AsyncClient

    def fake_client(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", fake_client)
    provider = DashScopeEmbeddingProvider(
        api_key="test-key",
        endpoint="https://example.invalid/v1/embeddings",
        model="text-embedding-v4",
        dimensions=3,
    )

    with pytest.raises(DashScopeError, match="向量维度不正确"):
        await provider.embed("面试准备")

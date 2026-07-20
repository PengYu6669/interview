import httpx


class DashScopeError(RuntimeError):
    pass


class DashScopeChatClient:
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        if not api_key:
            raise ValueError("尚未配置 DASHSCOPE_API_KEY")
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(90.0, connect=10.0),
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def complete(
        self,
        *,
        messages: list[dict[str, object]],
        max_tokens: int,
        tools: list[dict[str, object]] | None = None,
        json_mode: bool = True,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "enable_thinking": False,
        }
        if tools:
            payload["tools"] = tools
        elif json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise DashScopeError("阿里云模型请求失败") from exc
        if not isinstance(message, dict):
            raise DashScopeError("阿里云模型返回的消息结构无效")
        return message

    async def aclose(self) -> None:
        await self._client.aclose()


class DashScopeEmbeddingProvider:
    def __init__(self, *, api_key: str, endpoint: str, model: str, dimensions: int = 1024) -> None:
        if not api_key:
            raise ValueError("尚未配置 DASHSCOPE_API_KEY")
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        self._dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as client:
                response = await client.post(
                    self._endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "input": text,
                        "dimensions": self._dimensions,
                        "encoding_format": "float",
                    },
                )
                response.raise_for_status()
                vector = response.json()["data"][0]["embedding"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise DashScopeError("阿里云向量生成失败") from exc
        if not isinstance(vector, list) or len(vector) != self._dimensions:
            raise DashScopeError("阿里云返回的向量维度不正确")
        return [float(item) for item in vector]

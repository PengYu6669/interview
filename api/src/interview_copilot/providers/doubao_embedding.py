import httpx


class EmbeddingError(RuntimeError):
    pass


class DoubaoEmbeddingProvider:
    def __init__(self, *, api_key: str, endpoint: str, model: str, dimensions: int = 1024) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        self._dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        if not self._api_key or not self._model:
            raise EmbeddingError("豆包 Embedding 尚未配置")
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as client:
            try:
                response = await client.post(
                    self._endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "model": self._model,
                        "encoding_format": "float",
                        "dimensions": self._dimensions,
                        "input": [{"type": "text", "text": text}],
                    },
                )
                response.raise_for_status()
                payload = response.json()
                data = payload.get("data")
                vector = (
                    data.get("embedding") if isinstance(data, dict) else data[0].get("embedding")
                )
                if not isinstance(vector, list) or len(vector) != self._dimensions:
                    raise EmbeddingError("豆包返回的向量维度不正确")
                return [float(item) for item in vector]
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                raise EmbeddingError("豆包向量生成失败") from exc

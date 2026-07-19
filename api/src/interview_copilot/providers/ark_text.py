import asyncio
from typing import Any

from volcenginesdkarkruntime import Ark  # type: ignore[import-untyped]


class ArkTextClient:
    """Small vendor adapter that returns only the model's text content."""

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        if not api_key:
            raise ValueError("尚未配置 ARK_API_KEY")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.model = model

    async def complete(self, prompt: str, *, max_output_tokens: int = 6000) -> str:
        response = await asyncio.to_thread(
            self._complete_sync,
            prompt,
            max_output_tokens,
        )
        text = _response_text(response)
        if not text:
            raise RuntimeError("方舟返回了空的结构化结果")
        return text

    def _complete_sync(self, prompt: str, max_output_tokens: int) -> Any:
        client = Ark(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=(10.0, 90.0, 30.0, 30.0),
            max_retries=0,
        )
        try:
            return client.responses.create(
                model=self.model,
                instructions=(
                    "你是结构化数据处理器。严格遵循用户给出的 JSON Schema；"
                    "只返回一个合法 JSON 对象，不要解释、不要使用 Markdown。"
                ),
                input=[
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt}],
                    }
                ],
                max_output_tokens=max_output_tokens,
                thinking={"type": "disabled"},
                text={"format": {"type": "json_object"}},
                temperature=0,
                store=False,
            )
        finally:
            client.close()

    async def aclose(self) -> None:
        return None


def _response_text(response: Any) -> str:
    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return ""
    chunks: list[str] = []
    for item in output:
        content = getattr(item, "content", None)
        if not isinstance(content, list):
            continue
        for part in content:
            text = getattr(part, "text", None)
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks).strip()

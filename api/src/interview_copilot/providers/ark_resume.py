from interview_copilot.application.resume_extraction import ResumeExtractionError
from interview_copilot.domain.resume import ResumeProfile
from interview_copilot.providers.ark_text import ArkTextClient
from interview_copilot.providers.deepseek import DeepSeekResumeExtractor


class ArkResumeExtractor(DeepSeekResumeExtractor):
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._model = model
        self._owns_client = False
        self._ark = ArkTextClient(api_key=api_key, base_url=base_url, model=model)

    async def _complete(self, messages: list[dict[str, str]]) -> str:
        prompt = "\n\n".join(f"{message['role']}：{message['content']}" for message in messages)
        return await self._ark.complete(prompt, max_output_tokens=4000)

    async def extract(self, *, resume_text: str, jd: str, target_role: str) -> ResumeProfile:
        try:
            return await super().extract(
                resume_text=resume_text,
                jd=jd,
                target_role=target_role,
            )
        except ResumeExtractionError as exc:
            raise ResumeExtractionError(str(exc).replace("DeepSeek", "方舟")) from exc
        except Exception as exc:
            raise ResumeExtractionError("方舟结构化提取服务暂时不可用，请稍后重试") from exc

    async def aclose(self) -> None:
        await self._ark.aclose()

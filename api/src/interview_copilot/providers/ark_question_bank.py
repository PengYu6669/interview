from interview_copilot.providers.ark_text import ArkTextClient
from interview_copilot.providers.deepseek_question_bank import DeepSeekQuestionBankProvider


class ArkQuestionBankProvider(DeepSeekQuestionBankProvider):
    prompt_version = "ark-question-bank-v2"
    knowledge_section_limit = 2

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._ark = ArkTextClient(api_key=api_key, base_url=base_url, model=model)
        self._model = model
        self.model_name = model

    async def _chat(self, prompt: str) -> str:
        max_output_tokens = 3500 if ("抽取" in prompt or "合并" in prompt) else 6000
        try:
            return await self._ark.complete(prompt, max_output_tokens=max_output_tokens)
        except RuntimeError as exc:
            raise RuntimeError(str(exc).replace("DeepSeek", "方舟")) from exc

from interview_copilot.providers.ark_text import ArkTextClient
from interview_copilot.providers.deepseek_interview_planner import (
    DeepSeekInterviewPlanGenerator,
)


class ArkInterviewPlanGenerator(DeepSeekInterviewPlanGenerator):
    prompt_version = "interview-plan-v7-ark-compact"

    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self._ark = ArkTextClient(api_key=api_key, base_url=base_url, model=model)
        self.model_name = model

    async def _complete(self, prompt: str) -> str:
        return await self._ark.complete(prompt, max_output_tokens=6000)

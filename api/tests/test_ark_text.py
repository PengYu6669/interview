import pytest

from interview_copilot.domain.interviews import (
    InterviewPhasePlan,
    InterviewPlan,
    InterviewQuestionPlan,
)
from interview_copilot.domain.resume import ResumeProfile
from interview_copilot.providers.ark_interview_planner import ArkInterviewPlanGenerator
from interview_copilot.providers.ark_resume import ArkResumeExtractor
from interview_copilot.providers.ark_text import ArkTextClient


class FakePart:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeOutput:
    def __init__(self, text: str) -> None:
        self.content = [FakePart(text)]


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.output = [FakeOutput(text)]


@pytest.mark.asyncio
async def test_ark_text_client_extracts_only_output_text(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ArkTextClient(api_key="test-key", base_url="https://example.invalid", model="test")
    monkeypatch.setattr(
        client,
        "_complete_sync",
        lambda prompt, max_output_tokens: FakeResponse('{"ok":true}'),
    )

    assert await client.complete("return json") == '{"ok":true}'


@pytest.mark.asyncio
async def test_ark_resume_extractor_keeps_existing_schema_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ArkResumeExtractor(
        api_key="test-key", base_url="https://example.invalid", model="ark-test"
    )
    profile = ResumeProfile(target_role="AI 产品经理", summary="负责模型评测")

    async def fake_complete(prompt: str, *, max_output_tokens: int) -> str:
        del prompt
        del max_output_tokens
        return profile.model_dump_json()

    monkeypatch.setattr(provider._ark, "complete", fake_complete)

    result = await provider.extract(
        resume_text="负责模型评测",
        jd="需要 AI 产品经验",
        target_role="AI 产品经理",
    )

    assert result == profile


@pytest.mark.asyncio
async def test_ark_interview_planner_reuses_plan_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = ArkInterviewPlanGenerator(
        api_key="test-key", base_url="https://example.invalid", model="ark-test"
    )
    plan = InterviewPlan(
        target_role="AI 产品经理",
        summary="验证产品判断和模型评测能力",
        phases=[
            InterviewPhasePlan(
                name="项目深挖",
                kind="project",
                minutes=25,
                skills=["项目复盘"],
                questions=[
                    InterviewQuestionPlan(
                        prompt="说明你的核心贡献。",
                        intent="核实个人职责。",
                        skills=["项目复盘"],
                    )
                ],
            ),
            InterviewPhasePlan(
                name="候选人反问",
                kind="candidate_qa",
                minutes=5,
                skills=["岗位理解"],
                questions=[
                    InterviewQuestionPlan(
                        prompt="你有什么想了解的吗？",
                        intent="进行双向沟通。",
                        skills=["岗位理解"],
                    )
                ],
            ),
        ],
    )

    async def fake_complete(prompt: str, *, max_output_tokens: int) -> str:
        assert "面试计划设计器" in prompt
        assert max_output_tokens == 6000
        return plan.model_dump_json()

    monkeypatch.setattr(provider._ark, "complete", fake_complete)
    result = await provider.generate(
        resume_text="负责 AI 产品评测",
        jd="需要 AI 产品经验",
        target_role="AI 产品经理",
        target_company="",
        target_level="mid",
        interview_round="first",
        interview_type="comprehensive",
        mode="normal",
        duration_minutes=30,
        pressure_level=3,
        depth_level=4,
        guidance_level=3,
        question_bank_context=[],
        rag_context={"candidate": [], "job": [], "knowledge": []},
        training_focus="",
        extraction=None,
    )

    assert result == plan

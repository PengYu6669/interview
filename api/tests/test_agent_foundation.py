import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel

from interview_copilot.application.agent.coach import (
    ComparisonOutput,
    SecondAttemptAssessmentOutput,
    TrainingCoachAgent,
)
from interview_copilot.application.agent.skills import SkillRegistry, SkillRegistryError
from interview_copilot.application.agent.tools import (
    RetrieveEvidenceInput,
    RetrieveEvidenceTool,
    ToolAuditEvent,
    ToolCall,
    ToolContext,
    ToolExecutionError,
    ToolExecutor,
    ToolInput,
    ToolRegistry,
)
from interview_copilot.domain.coaching import CoachingDecision
from interview_copilot.providers.qwen_agent import QwenFunctionCallingClient


class EchoInput(ToolInput):
    value: str


class EchoOutput(BaseModel):
    value: str


class EmptyThenValidClient(QwenFunctionCallingClient):
    def __init__(self) -> None:
        registry = ToolRegistry([])
        super().__init__(
            api_key="test-key",
            base_url="https://example.test",
            model="test-model",
            registry=registry,
            executor=ToolExecutor(registry),
        )
        self.calls = 0

    async def _chat(self, **_: object) -> dict[str, object]:
        self.calls += 1
        if self.calls == 1:
            return {"content": ""}
        return {"content": '{"value":"ok"}'}


class EchoTool:
    name = "echo"
    description = "返回输入值"
    input_model = EchoInput
    output_model = EchoOutput

    async def execute(self, context: ToolContext, arguments: ToolInput) -> BaseModel:
        del context
        request = EchoInput.model_validate(arguments)
        return EchoOutput(value=request.value)


@pytest.mark.asyncio
async def test_agent_retries_one_empty_final_response() -> None:
    client = EmptyThenValidClient()

    output = await client.run_json(
        instructions="测试",
        user_data={"value": "untrusted"},
        context=ToolContext(user_id=uuid4(), request_id=uuid4()),
        allowed_tools=set(),
        output_model=EchoOutput,
        max_tool_calls=0,
        max_output_tokens=500,
    )

    assert output.value == "ok"
    assert client.calls == 2


class CapturingAuditSink:
    def __init__(self) -> None:
        self.events: list[ToolAuditEvent] = []

    async def record(self, event: ToolAuditEvent) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_retrieval_tool_enforces_hard_source_allowlist() -> None:
    allowed_id = uuid4()
    blocked_id = uuid4()

    class FakeSearch:
        source_ids: list = []

        async def search(self, **kwargs: object) -> list:
            self.source_ids = list(kwargs["source_ids"])  # type: ignore[arg-type]
            return []

    search = FakeSearch()
    tool = RetrieveEvidenceTool(
        search,  # type: ignore[arg-type]
        name="retrieve_knowledge_evidence",
        description="测试",
        corpus_type="knowledge",
    )
    context = ToolContext(
        user_id=uuid4(),
        request_id=uuid4(),
        allowed_source_ids=frozenset({allowed_id}),
    )

    await tool.execute(
        context,
        RetrieveEvidenceInput(query="检索", source_ids=[allowed_id]),
    )
    assert search.source_ids == [allowed_id]
    with pytest.raises(ToolExecutionError, match="未授权"):
        await tool.execute(
            context,
            RetrieveEvidenceInput(query="越权检索", source_ids=[blocked_id]),
        )
    with pytest.raises(ToolExecutionError, match="没有授权"):
        await tool.execute(
            ToolContext(user_id=uuid4(), request_id=uuid4()),
            RetrieveEvidenceInput(query="空授权"),
        )


def test_skill_registry_progressively_loads_metadata_then_content() -> None:
    registry = SkillRegistry()
    metadata = registry.list_metadata()

    assert [item.name for item in metadata] == [
        "business-sense-coach",
        "career-planning-coach",
        "structured-expression-coach",
    ]
    activated = registry.activate("structured-expression-coach")
    assert "不虚构项目、数字、职责" in activated.instructions
    assert activated.rubric["version"] == "structured-expression-rubric-v2"
    assert len(activated.instructions.splitlines()) <= 200
    business = registry.activate("business-sense-coach")
    assert business.metadata.version == "2.0.0"
    assert business.rubric["version"] == "business-sense-rubric-v2"
    planning = registry.activate("career-planning-coach")
    assert planning.metadata.version == "1.1.0"
    assert planning.rubric["version"] == "career-planning-rubric-v1.1"
    assert "不是商业百科" in business.instructions
    assert len(business.instructions.splitlines()) <= 200


def test_skill_registry_rejects_path_traversal(tmp_path: Path) -> None:
    registry = SkillRegistry(tmp_path)
    with pytest.raises(SkillRegistryError, match="名称格式"):
        registry.activate("../private")


@pytest.mark.asyncio
async def test_tool_executor_validates_allowlist_arguments_and_output() -> None:
    registry = ToolRegistry([EchoTool()])
    definitions = registry.openai_definitions({"echo"})
    schema = definitions[0]["function"]
    assert isinstance(schema, dict)
    assert schema["name"] == "echo"
    audit = CapturingAuditSink()
    executor = ToolExecutor(registry, audit_sink=audit)
    session_id = uuid4()
    context = ToolContext(
        user_id=uuid4(), request_id=uuid4(), session_id=session_id
    )
    result = await executor.execute(
        ToolCall(id="call-1", name="echo", arguments=json.dumps({"value": "中文"})),
        context=context,
        allowed_tools={"echo"},
    )
    assert json.loads(result.content) == {"value": "中文"}
    assert audit.events[0].succeeded is True
    assert audit.events[0].session_id == session_id
    assert audit.events[0].argument_summary == {
        "value": {"type": "string", "characters": 2}
    }
    assert "中文" not in json.dumps(audit.events[0].argument_summary, ensure_ascii=False)

    with pytest.raises(ToolExecutionError, match="不允许"):
        await executor.execute(
            ToolCall(id="call-2", name="echo", arguments='{"value":"x"}'),
            context=context,
            allowed_tools=set(),
        )
    with pytest.raises(ToolExecutionError, match="参数无效"):
        await executor.execute(
            ToolCall(id="call-3", name="echo", arguments='{"value":"x","user_id":"伪造"}'),
            context=context,
            allowed_tools={"echo"},
        )
    assert [event.succeeded for event in audit.events] == [True, False, False]


@pytest.mark.asyncio
async def test_tool_executor_enforces_timeout() -> None:
    class SlowTool(EchoTool):
        name = "slow"

        async def execute(self, context: ToolContext, arguments: ToolInput) -> BaseModel:
            del context, arguments
            await asyncio.sleep(0.05)
            return EchoOutput(value="late")

    registry = ToolRegistry([SlowTool()])
    executor = ToolExecutor(registry, timeout_seconds=0.001)
    with pytest.raises(ToolExecutionError, match="超时"):
        await executor.execute(
            ToolCall(id="call-4", name="slow", arguments='{"value":"x"}'),
            context=ToolContext(user_id=uuid4(), request_id=uuid4()),
            allowed_tools={"slow"},
        )


@pytest.mark.asyncio
async def test_qwen_agent_executes_bounded_tool_call_then_validates_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FinalOutput(BaseModel):
        answer: str

    registry = ToolRegistry([EchoTool()])
    executor = ToolExecutor(registry)
    client = QwenFunctionCallingClient(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
        registry=registry,
        executor=executor,
    )
    requests: list[list[dict[str, object]]] = []

    async def fake_chat(
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        max_output_tokens: int,
    ) -> dict[str, object]:
        del tools, max_output_tokens
        requests.append(list(messages))
        if len(requests) == 1:
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "echo", "arguments": '{"value":"证据"}'},
                    }
                ],
            }
        return {"content": '{"answer":"已读取证据"}'}

    monkeypatch.setattr(client, "_chat", fake_chat)
    result = await client.run_json(
        instructions="完成测试任务。",
        user_data={"question": "测试"},
        context=ToolContext(user_id=uuid4(), request_id=uuid4()),
        allowed_tools={"echo"},
        output_model=FinalOutput,
        max_tool_calls=1,
    )

    assert result.answer == "已读取证据"
    assert any(message.get("role") == "tool" for message in requests[1])


@pytest.mark.asyncio
async def test_qwen_agent_repairs_invalid_json_without_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FinalOutput(BaseModel):
        answer: str

    registry = ToolRegistry([EchoTool()])
    client = QwenFunctionCallingClient(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
        registry=registry,
        executor=ToolExecutor(registry),
    )
    requests: list[tuple[list[dict[str, object]], list[dict[str, object]]]] = []

    async def fake_chat(
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        max_output_tokens: int,
    ) -> dict[str, object]:
        del max_output_tokens
        requests.append((list(messages), list(tools)))
        if len(requests) == 1:
            return {"content": '{"answer":'}
        return {"content": '{"answer":"修复成功"}'}

    monkeypatch.setattr(client, "_chat", fake_chat)
    result = await client.run_json(
        instructions="完成测试任务。",
        user_data={"question": "测试"},
        context=ToolContext(user_id=uuid4(), request_id=uuid4()),
        allowed_tools={"echo"},
        output_model=FinalOutput,
        max_tool_calls=1,
    )

    assert result.answer == "修复成功"
    assert requests[0][1]
    assert requests[1][1] == []
    assert requests[1][0][-1]["role"] == "user"


def test_training_coach_aligns_punctuation_to_exact_answer_substring() -> None:
    answer = "我负责核心模块，最终提升 20%！"

    quote = TrainingCoachAgent._align_quote("我负责核心模块最终提升20。", answer)

    assert quote == "我负责核心模块，最终提升 20"
    assert quote in answer


def test_training_coach_downgrades_unverifiable_evidence() -> None:
    decision = CoachingDecision.model_validate(
        {
            "action": "complete",
            "coach_reply": "已完成。",
            "assessments": [
                {
                    "key": "conclusion",
                    "status": "observed",
                    "level": 4,
                    "evidence_quote": "回答中不存在的结论",
                    "feedback": "结论清楚。",
                    "confidence": 0.9,
                }
            ],
            "summary": "本轮总结。",
            "evidence_segments": [
                {
                    "key": "conclusion",
                    "label": "结论",
                    "evidence_quote": "另一段不存在的内容",
                }
            ],
        }
    )

    sanitized = TrainingCoachAgent._sanitize_decision_evidence(
        decision,
        current_answer="这是用户真正提交的回答。",
        first_answer="",
    )

    assessment = sanitized.assessments[0]
    assert assessment.status == "evidence_insufficient"
    assert assessment.level is None
    assert assessment.evidence_quote is None
    assert assessment.confidence == 0.4
    assert sanitized.evidence_segments == []


@pytest.mark.asyncio
async def test_training_coach_splits_second_attempt_assessment_and_comparison() -> None:
    class StubClient:
        model_name = "test-model"
        prompt_version = "test-prompt-v2"

        def __init__(self) -> None:
            self.output_models: list[type[BaseModel]] = []

        async def run_json(self, **kwargs: object) -> BaseModel:
            output_model = kwargs["output_model"]
            assert isinstance(output_model, type)
            self.output_models.append(output_model)
            if output_model is SecondAttemptAssessmentOutput:
                return SecondAttemptAssessmentOutput.model_validate(
                    {
                        "coach_reply": "第二次回答更直接。",
                        "assessments": [
                            {
                                "key": "conclusion",
                                "status": "observed",
                                "level": 4,
                                "evidence_quote": "我先给结论",
                                "feedback": "结论已前置。",
                                "confidence": 0.9,
                            }
                        ],
                        "summary": "当前回答评价完成。",
                        "evidence_segments": [
                            {
                                "key": "conclusion",
                                "label": "结论",
                                "evidence_quote": "我先给结论",
                            }
                        ],
                    }
                )
            assert output_model is ComparisonOutput
            return ComparisonOutput.model_validate(
                {
                    "comparison": {
                        "items": [
                            {
                                "dimension": "conclusion",
                                "change": "improved",
                                "before_level": 2,
                                "after_level": 4,
                                "before_quote": "我介绍一下背景",
                                "after_quote": "我先给结论",
                                "explanation": "重答先给出了明确结论。",
                            }
                        ],
                        "overall_summary": "结论前置有明显改善。",
                    },
                    "next_practice": {
                        "focus": "用一句话先回答问题",
                        "recommended_difficulty": "assisted",
                        "estimated_minutes": 10,
                    },
                }
            )

    client = StubClient()
    agent = TrainingCoachAgent(SkillRegistry(), client)  # type: ignore[arg-type]
    decision = await agent.evaluate(
        mode="structured_expression",
        user_data={
            "本次作答序号": 2,
            "用户回答": "我先给结论，然后补充行动和结果。",
            "第一次回答": "我介绍一下背景，然后再说明项目过程。",
            "训练任务": {"dimensions": ["conclusion"]},
        },
        user_id=uuid4(),
        request_id=uuid4(),
        final_turn=True,
    )

    assert client.output_models == [SecondAttemptAssessmentOutput, ComparisonOutput]
    assert decision.action == "complete"
    assert decision.comparison is not None
    assert decision.comparison.items[0].change == "improved"
    assert decision.next_practice is not None
    assert decision.next_practice.estimated_minutes == 10

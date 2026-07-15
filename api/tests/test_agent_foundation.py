import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel

from interview_copilot.application.agent.skills import SkillRegistry, SkillRegistryError
from interview_copilot.application.agent.tools import (
    ToolAuditEvent,
    ToolCall,
    ToolContext,
    ToolExecutionError,
    ToolExecutor,
    ToolInput,
    ToolRegistry,
)
from interview_copilot.providers.deepseek_agent import DeepSeekFunctionCallingClient


class EchoInput(ToolInput):
    value: str


class EchoOutput(BaseModel):
    value: str


class EchoTool:
    name = "echo"
    description = "返回输入值"
    input_model = EchoInput
    output_model = EchoOutput

    async def execute(self, context: ToolContext, arguments: ToolInput) -> BaseModel:
        del context
        request = EchoInput.model_validate(arguments)
        return EchoOutput(value=request.value)


class CapturingAuditSink:
    def __init__(self) -> None:
        self.events: list[ToolAuditEvent] = []

    async def record(self, event: ToolAuditEvent) -> None:
        self.events.append(event)


def test_skill_registry_progressively_loads_metadata_then_content() -> None:
    registry = SkillRegistry()
    metadata = registry.list_metadata()

    assert [item.name for item in metadata] == [
        "business-sense-coach",
        "structured-expression-coach",
    ]
    activated = registry.activate("structured-expression-coach")
    assert "不替用户编造" in activated.instructions
    assert activated.rubric["version"] == "structured-expression-rubric-v1"


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
async def test_deepseek_agent_executes_bounded_tool_call_then_validates_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FinalOutput(BaseModel):
        answer: str

    registry = ToolRegistry([EchoTool()])
    executor = ToolExecutor(registry)
    client = DeepSeekFunctionCallingClient(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
        registry=registry,
        executor=executor,
    )
    requests: list[list[dict[str, object]]] = []

    async def fake_chat(
        *, messages: list[dict[str, object]], tools: list[dict[str, object]]
    ) -> dict[str, object]:
        del tools
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

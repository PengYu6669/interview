import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from interview_copilot.application.retrieval.search import RagSearchService
from interview_copilot.domain.retrieval import CorpusType, RetrievedEvidence


class ToolExecutionError(RuntimeError):
    pass


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RetrieveEvidenceInput(ToolInput):
    query: str = Field(min_length=1, max_length=2_000)
    source_ids: list[UUID] = Field(default_factory=list, max_length=30)
    limit: int = Field(default=6, ge=1, le=12)


class RetrieveEvidenceOutput(BaseModel):
    evidence: list[RetrievedEvidence]


@dataclass(frozen=True, slots=True)
class ToolContext:
    user_id: UUID
    request_id: UUID
    session_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ToolAuditEvent:
    user_id: UUID
    request_id: UUID
    session_id: UUID | None
    tool_call_id: str
    tool_name: str
    argument_summary: dict[str, object]
    succeeded: bool
    duration_ms: int
    error_type: str | None
    created_at: datetime


class ToolAuditSink(Protocol):
    async def record(self, event: ToolAuditEvent) -> None: ...


class AgentTool(Protocol):
    name: str
    description: str
    input_model: type[ToolInput]
    output_model: type[BaseModel]

    async def execute(self, context: ToolContext, arguments: ToolInput) -> BaseModel: ...


class RetrieveEvidenceTool:
    input_model: type[ToolInput] = RetrieveEvidenceInput
    output_model: type[BaseModel] = RetrieveEvidenceOutput

    def __init__(
        self,
        search: RagSearchService,
        *,
        name: str,
        description: str,
        corpus_type: CorpusType,
        source_types: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.description = description
        self._search = search
        self._corpus_type = corpus_type
        self._source_types = source_types

    async def execute(self, context: ToolContext, arguments: ToolInput) -> BaseModel:
        request = RetrieveEvidenceInput.model_validate(arguments)
        evidence = await self._search.search(
            user_id=context.user_id,
            query=request.query,
            corpus_types=[self._corpus_type],
            source_types=self._source_types,
            source_ids=request.source_ids,
            limit=request.limit,
        )
        return RetrieveEvidenceOutput(evidence=evidence)


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=100)
    arguments: str = Field(max_length=20_000)


class ToolCallResult(BaseModel):
    tool_call_id: str
    name: str
    content: str


class ToolRegistry:
    def __init__(self, tools: list[AgentTool]) -> None:
        self._tools = {tool.name: tool for tool in tools}
        if len(self._tools) != len(tools):
            raise ValueError("Agent Tool 名称不能重复")

    def get(self, name: str) -> AgentTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolExecutionError(f"不允许调用工具：{name}") from exc

    def openai_definitions(self, allowed_tools: set[str]) -> list[dict[str, object]]:
        unknown = allowed_tools.difference(self._tools)
        if unknown:
            raise ToolExecutionError(f"工具白名单包含未注册项：{sorted(unknown)}")
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_model.model_json_schema(),
                },
            }
            for name, tool in self._tools.items()
            if name in allowed_tools
        ]


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        timeout_seconds: float = 20,
        max_result_characters: int = 30_000,
        audit_sink: ToolAuditSink | None = None,
    ) -> None:
        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._max_result_characters = max_result_characters
        self._audit_sink = audit_sink

    async def execute(
        self,
        call: ToolCall,
        *,
        context: ToolContext,
        allowed_tools: set[str],
    ) -> ToolCallResult:
        started_at = perf_counter()
        argument_summary: dict[str, object] = {
            "payload": {"type": "unvalidated_json", "characters": len(call.arguments)}
        }
        try:
            if call.name not in allowed_tools:
                raise ToolExecutionError(f"本轮不允许调用工具：{call.name}")
            tool = self._registry.get(call.name)
            raw_arguments = json.loads(call.arguments)
            arguments = tool.input_model.model_validate(raw_arguments)
            argument_summary = _summarize_arguments(arguments)
            async with asyncio.timeout(self._timeout_seconds):
                raw_output = await tool.execute(context, arguments)
            output = tool.output_model.model_validate(raw_output)
            content = output.model_dump_json()
            if len(content) > self._max_result_characters:
                raise ToolExecutionError(f"工具 {call.name} 返回内容超过限制")
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            error = ToolExecutionError(f"工具 {call.name} 的参数无效或返回结构无效")
            await self._audit(
                call, context, argument_summary, started_at, error_type=type(exc).__name__
            )
            raise error from exc
        except TimeoutError as exc:
            await self._audit(
                call, context, argument_summary, started_at, error_type="TimeoutError"
            )
            raise ToolExecutionError(f"工具 {call.name} 执行超时") from exc
        except ToolExecutionError as exc:
            await self._audit(
                call, context, argument_summary, started_at, error_type=type(exc).__name__
            )
            raise
        except Exception as exc:
            await self._audit(
                call, context, argument_summary, started_at, error_type=type(exc).__name__
            )
            raise ToolExecutionError(f"工具 {call.name} 执行失败") from exc
        await self._audit(call, context, argument_summary, started_at, error_type=None)
        return ToolCallResult(tool_call_id=call.id, name=call.name, content=content)

    async def _audit(
        self,
        call: ToolCall,
        context: ToolContext,
        argument_summary: dict[str, object],
        started_at: float,
        *,
        error_type: str | None,
    ) -> None:
        if not self._audit_sink:
            return
        event = ToolAuditEvent(
            user_id=context.user_id,
            request_id=context.request_id,
            session_id=context.session_id,
            tool_call_id=call.id,
            tool_name=call.name,
            argument_summary=argument_summary,
            succeeded=error_type is None,
            duration_ms=max(0, round((perf_counter() - started_at) * 1000)),
            error_type=error_type,
            created_at=datetime.now(UTC),
        )
        try:
            await self._audit_sink.record(event)
        except Exception as exc:
            raise ToolExecutionError("Agent 工具审计写入失败") from exc


def _summarize_arguments(arguments: ToolInput) -> dict[str, object]:
    summary: dict[str, object] = {}
    for name, value in arguments.model_dump(mode="python").items():
        if isinstance(value, str):
            summary[name] = {"type": "string", "characters": len(value)}
        elif isinstance(value, list):
            summary[name] = {"type": "list", "items": len(value)}
        elif isinstance(value, (int, float, bool)) or value is None:
            summary[name] = {"type": type(value).__name__, "value": value}
        else:
            summary[name] = {"type": type(value).__name__}
    return summary


def build_retrieval_tool_registry(search: RagSearchService) -> ToolRegistry:
    return ToolRegistry(
        [
            RetrieveEvidenceTool(
                search,
                name="retrieve_candidate_evidence",
                description="检索当前用户的简历、项目经历和历史回答证据",
                corpus_type="candidate",
            ),
            RetrieveEvidenceTool(
                search,
                name="retrieve_job_evidence",
                description="检索当前用户目标岗位、JD 和业务上下文证据",
                corpus_type="job",
            ),
            RetrieveEvidenceTool(
                search,
                name="retrieve_knowledge_evidence",
                description="检索题库和已审核知识资料，返回可引用的技术或产品证据",
                corpus_type="knowledge",
            ),
        ]
    )

import json
from typing import Literal, TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from interview_copilot.application.agent.skills import ActivatedSkill, SkillRegistry
from interview_copilot.application.agent.tools import ToolContext
from interview_copilot.domain.coaching import (
    CoachingAttemptComparison,
    CoachingDecision,
    CoachingEvidenceSegment,
    CoachingMode,
    CoachingNextPractice,
    CoachingPriorityGap,
    CoachingTaskPlan,
    DimensionAssessment,
)
from interview_copilot.providers.deepseek_agent import (
    DeepSeekAgentError,
    DeepSeekFunctionCallingClient,
)

_SKILL_BY_MODE: dict[CoachingMode, str] = {
    "structured_expression": "structured-expression-coach",
    "business_sense": "business-sense-coach",
}
_RETRIEVAL_TOOLS = {
    "retrieve_candidate_evidence",
    "retrieve_job_evidence",
    "retrieve_knowledge_evidence",
}


class FirstAttemptOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coach_reply: str = Field(min_length=1, max_length=1_000)
    next_question: str = Field(min_length=1, max_length=1_500)
    assessments: list[DimensionAssessment] = Field(min_length=1, max_length=8)
    summary: str = Field(min_length=1, max_length=1_000)
    evidence_segments: list[CoachingEvidenceSegment] = Field(default_factory=list, max_length=12)
    priority_gaps: list[CoachingPriorityGap] = Field(min_length=1, max_length=2)


class SecondAttemptAssessmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coach_reply: str = Field(min_length=1, max_length=1_000)
    assessments: list[DimensionAssessment] = Field(min_length=1, max_length=8)
    summary: str = Field(min_length=1, max_length=1_000)
    evidence_segments: list[CoachingEvidenceSegment] = Field(default_factory=list, max_length=12)


class ComparisonOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comparison: CoachingAttemptComparison
    next_practice: CoachingNextPractice


class CoachState(TypedDict, total=False):
    operation: Literal["plan", "evaluate"]
    mode: CoachingMode
    user_data: dict[str, object]
    tool_context: ToolContext
    skill: ActivatedSkill
    task: CoachingTaskPlan
    decision: CoachingDecision


class TrainingCoachAgent:
    def __init__(
        self,
        skill_registry: SkillRegistry,
        client: DeepSeekFunctionCallingClient,
    ) -> None:
        self._skills = skill_registry
        self._client = client
        self.model_name = client.model_name
        self.prompt_version = client.prompt_version
        self._graph = self._build_graph()

    async def plan(
        self,
        *,
        mode: CoachingMode,
        user_data: dict[str, object],
        user_id: UUID,
        request_id: UUID,
        session_id: UUID | None = None,
    ) -> tuple[ActivatedSkill, CoachingTaskPlan]:
        allowed_source_ids = self._source_ids(user_data)
        result = await self._graph.ainvoke(
            CoachState(
                operation="plan",
                mode=mode,
                user_data=user_data,
                tool_context=ToolContext(
                    user_id=user_id,
                    request_id=request_id,
                    session_id=session_id,
                    allowed_source_ids=allowed_source_ids,
                ),
            )
        )
        return cast(ActivatedSkill, result["skill"]), cast(CoachingTaskPlan, result["task"])

    async def evaluate(
        self,
        *,
        mode: CoachingMode,
        user_data: dict[str, object],
        user_id: UUID,
        request_id: UUID,
        final_turn: bool,
        session_id: UUID | None = None,
    ) -> CoachingDecision:
        data = {**user_data, "这是最后一轮": final_turn}
        result = await self._graph.ainvoke(
            CoachState(
                operation="evaluate",
                mode=mode,
                user_data=data,
                tool_context=ToolContext(
                    user_id=user_id, request_id=request_id, session_id=session_id
                ),
            )
        )
        decision = cast(CoachingDecision, result["decision"])
        if final_turn and decision.action != "complete":
            raise DeepSeekAgentError("训练达到轮数上限，但 Agent 未正确结束训练")
        current_answer = str(user_data.get("用户回答", ""))
        first_answer = str(user_data.get("第一次回答") or "")
        decision = self._align_decision_quotes(
            decision, current_answer=current_answer, first_answer=first_answer
        )
        decision = self._sanitize_decision_evidence(
            decision, current_answer=current_answer, first_answer=first_answer
        )
        self._validate_decision_evidence(
            decision,
            current_answer=current_answer,
            first_answer=first_answer,
        )
        return decision

    @staticmethod
    def _source_ids(user_data: dict[str, object]) -> frozenset[UUID]:
        raw_ids = user_data.get("允许使用的资料编号")
        if not isinstance(raw_ids, list):
            return frozenset()
        parsed: set[UUID] = set()
        for raw_id in raw_ids:
            try:
                parsed.add(UUID(str(raw_id)))
            except ValueError as exc:
                raise DeepSeekAgentError("训练资料编号格式不正确") from exc
        return frozenset(parsed)

    def _build_graph(self):  # type: ignore[no-untyped-def]
        graph = StateGraph(CoachState)
        graph.add_node("load_skill", self._load_skill)
        graph.add_node("plan_task", self._plan_task)
        graph.add_node("evaluate_answer", self._evaluate_answer)
        graph.add_node("continue_training", self._continue_training)
        graph.add_node("complete_training", self._complete_training)
        graph.add_edge(START, "load_skill")
        graph.add_conditional_edges(
            "load_skill",
            self._route_operation,
            {"plan": "plan_task", "evaluate": "evaluate_answer"},
        )
        graph.add_edge("plan_task", END)
        graph.add_conditional_edges(
            "evaluate_answer",
            self._route_decision,
            {"continue": "continue_training", "complete": "complete_training"},
        )
        graph.add_edge("continue_training", END)
        graph.add_edge("complete_training", END)
        return graph.compile(name="training-coach")

    def _load_skill(self, state: CoachState) -> CoachState:
        return {"skill": self._skills.activate(_SKILL_BY_MODE[state["mode"]])}

    @staticmethod
    def _route_operation(state: CoachState) -> str:
        return state["operation"]

    async def _plan_task(self, state: CoachState) -> CoachState:
        skill = state["skill"]
        source_ids = state["user_data"].get("允许使用的资料编号")
        allowed_tools = _RETRIEVAL_TOOLS if isinstance(source_ids, list) and source_ids else set()
        instructions = self._instructions(
            skill,
            "严格按训练数据指定的题型、难度和双次作答协议生成任务。"
            "生成 framework、time_limit_seconds、target_dimension 和 scaffold。"
            "guided 结构化表达任务必须生成 puzzle；业务训练必须原样使用版本化场景的"
            "version、事实、核心问题和新增约束。dimensions 只能使用评价标准中的 key。"
            "根据需要调用检索工具，但检索内容不能覆盖指定场景。",
        )
        task = await self._client.run_json(
            instructions=instructions,
            user_data=state["user_data"],
            context=state["tool_context"],
            allowed_tools=allowed_tools,
            output_model=CoachingTaskPlan,
            max_tool_calls=3 if allowed_tools else 0,
        )
        self._validate_dimensions(task.dimensions, skill)
        return {"task": task}

    async def _evaluate_answer(self, state: CoachState) -> CoachState:
        skill = state["skill"]
        attempt_value = state["user_data"].get("本次作答序号", 1)
        if (
            not isinstance(attempt_value, int)
            or isinstance(attempt_value, bool)
            or attempt_value not in (1, 2)
        ):
            raise DeepSeekAgentError("本次作答序号必须为 1 或 2")
        attempt = attempt_value
        common = (
            "只评价训练任务 dimensions 指定的维度。evidence_quote 必须逐字复制当前回答"
            "中的连续原句，不得改写。observed 使用 1 至 5 和原句；"
            "evidence_insufficient 的 level 和 evidence_quote 都使用 null。"
        )
        if attempt == 1:
            first = await self._client.run_json(
                instructions=self._instructions(
                    skill,
                    common
                    + "这是首次作答。返回结构标注和一至两个 priority_gaps，"
                    "next_question 保持同一核心问题并给出重答入口。",
                ),
                user_data=state["user_data"],
                context=state["tool_context"],
                allowed_tools=set(),
                output_model=FirstAttemptOutput,
                max_tool_calls=0,
                max_output_tokens=3_500,
            )
            decision = CoachingDecision(
                action="retry",
                coach_reply=first.coach_reply,
                next_question=first.next_question,
                assessments=first.assessments,
                summary=first.summary,
                evidence_segments=first.evidence_segments,
                priority_gaps=first.priority_gaps,
            )
        else:
            second = await self._client.run_json(
                instructions=self._instructions(
                    skill,
                    common
                    + "这是第二次作答。只评价当前回答并简洁总结，不在本步生成前后对比。",
                ),
                user_data=state["user_data"],
                context=state["tool_context"],
                allowed_tools=set(),
                output_model=SecondAttemptAssessmentOutput,
                max_tool_calls=0,
                max_output_tokens=3_500,
            )
            comparison = await self._client.run_json(
                instructions=self._instructions(
                    skill,
                    "比较第一次与第二次回答，只比较首次 priority_gaps、target_dimension 及"
                    "最关键的改善，最多三项。before_quote 只复制第一次回答，after_quote "
                    "只复制第二次回答。无法获得双侧原句时 change=insufficient。"
                    "生成一个下一次 10 分钟训练建议。",
                ),
                user_data={
                    **state["user_data"],
                    "第二次评价": second.model_dump(mode="json"),
                },
                context=state["tool_context"],
                allowed_tools=set(),
                output_model=ComparisonOutput,
                max_tool_calls=0,
                max_output_tokens=3_500,
            )
            decision = CoachingDecision(
                action="complete",
                coach_reply=second.coach_reply,
                next_question=None,
                assessments=second.assessments,
                summary=second.summary,
                evidence_segments=second.evidence_segments,
                comparison=comparison.comparison,
                next_practice=comparison.next_practice,
            )
        returned_dimensions = [item.key for item in decision.assessments]
        returned_dimensions.extend(item.dimension for item in decision.priority_gaps)
        if decision.comparison:
            returned_dimensions.extend(
                item.dimension for item in decision.comparison.items
            )
        self._validate_dimensions(returned_dimensions, skill)
        task = state["user_data"].get("训练任务")
        if isinstance(task, dict):
            selected = task.get("dimensions")
            if isinstance(selected, list):
                unexpected = set(returned_dimensions).difference(str(item) for item in selected)
                if unexpected:
                    raise DeepSeekAgentError(
                        f"Agent 评价了本次任务之外的维度：{sorted(unexpected)}"
                    )
        return {"decision": decision}

    @staticmethod
    def _route_decision(state: CoachState) -> str:
        return "complete" if state["decision"].action == "complete" else "continue"

    @staticmethod
    def _continue_training(state: CoachState) -> CoachState:
        if not state["decision"].next_question:
            raise DeepSeekAgentError("继续训练分支缺少下一题")
        return {}

    @staticmethod
    def _complete_training(state: CoachState) -> CoachState:
        if state["decision"].next_question is not None:
            raise DeepSeekAgentError("完成训练分支仍包含下一题")
        return {}

    @staticmethod
    def _instructions(skill: ActivatedSkill, phase_instruction: str) -> str:
        return (
            f"{skill.instructions}\n\n"
            f"当前 Skill：{skill.metadata.name}@{skill.metadata.version}\n"
            f"评价标准：{json.dumps(skill.rubric, ensure_ascii=False)}\n"
            f"当前阶段：{phase_instruction}"
        )

    @staticmethod
    def _validate_dimensions(dimensions: list[str], skill: ActivatedSkill) -> None:
        allowed = {str(item["key"]) for item in skill.rubric.get("dimensions", [])}
        unknown = set(dimensions).difference(allowed)
        if unknown:
            raise DeepSeekAgentError(f"Agent 返回了未定义的评价维度：{sorted(unknown)}")

    @staticmethod
    def _validate_decision_evidence(
        decision: CoachingDecision, *, current_answer: str, first_answer: str
    ) -> None:
        for assessment in decision.assessments:
            if assessment.evidence_quote and assessment.evidence_quote not in current_answer:
                raise DeepSeekAgentError(f"评价维度 {assessment.key} 引用了回答中不存在的证据")
        for segment in decision.evidence_segments:
            if segment.evidence_quote not in current_answer:
                raise DeepSeekAgentError(f"结构标注 {segment.key} 引用了回答中不存在的证据")
        if not decision.comparison:
            return
        for item in decision.comparison.items:
            if item.before_quote and item.before_quote not in first_answer:
                raise DeepSeekAgentError(f"对比维度 {item.dimension} 的首次证据不存在")
            if item.after_quote and item.after_quote not in current_answer:
                raise DeepSeekAgentError(f"对比维度 {item.dimension} 的重答证据不存在")

    @classmethod
    def _align_decision_quotes(
        cls,
        decision: CoachingDecision,
        *,
        current_answer: str,
        first_answer: str,
    ) -> CoachingDecision:
        payload = decision.model_dump(mode="python")
        for assessment in payload["assessments"]:
            assessment["evidence_quote"] = cls._align_quote(
                assessment.get("evidence_quote"), current_answer
            )
        for segment in payload["evidence_segments"]:
            segment["evidence_quote"] = cls._align_quote(
                segment.get("evidence_quote"), current_answer
            )
        comparison = payload.get("comparison")
        if comparison:
            for item in comparison["items"]:
                item["before_quote"] = cls._align_quote(
                    item.get("before_quote"), first_answer
                )
                item["after_quote"] = cls._align_quote(
                    item.get("after_quote"), current_answer
                )
        return CoachingDecision.model_validate(payload)

    @classmethod
    def _sanitize_decision_evidence(
        cls,
        decision: CoachingDecision,
        *,
        current_answer: str,
        first_answer: str,
    ) -> CoachingDecision:
        payload = decision.model_dump(mode="python")
        for assessment in payload["assessments"]:
            quote = assessment.get("evidence_quote")
            if quote and quote not in current_answer:
                assessment.update(
                    status="evidence_insufficient",
                    level=None,
                    evidence_quote=None,
                    confidence=min(float(assessment.get("confidence", 0)), 0.4),
                )
        payload["evidence_segments"] = [
            item
            for item in payload["evidence_segments"]
            if item.get("evidence_quote") in current_answer
        ]
        comparison = payload.get("comparison")
        if comparison:
            for item in comparison["items"]:
                before_valid = not item.get("before_quote") or item["before_quote"] in first_answer
                after_valid = not item.get("after_quote") or item["after_quote"] in current_answer
                if not before_valid or not after_valid:
                    item.update(
                        change="insufficient",
                        before_level=None,
                        after_level=None,
                        before_quote=item.get("before_quote") if before_valid else None,
                        after_quote=item.get("after_quote") if after_valid else None,
                    )
        return CoachingDecision.model_validate(payload)

    @staticmethod
    def _align_quote(quote: str | None, answer: str) -> str | None:
        if not quote or quote in answer:
            return quote
        normalized_answer: list[str] = []
        answer_indexes: list[int] = []
        for index, char in enumerate(answer):
            if char.isalnum():
                normalized_answer.append(char.casefold())
                answer_indexes.append(index)
        normalized_quote = "".join(char.casefold() for char in quote if char.isalnum())
        if not normalized_quote:
            return quote
        start = "".join(normalized_answer).find(normalized_quote)
        if start < 0:
            return quote
        end = start + len(normalized_quote) - 1
        return answer[answer_indexes[start] : answer_indexes[end] + 1]

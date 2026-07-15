import json
from typing import Literal, TypedDict, cast
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from interview_copilot.application.agent.skills import ActivatedSkill, SkillRegistry
from interview_copilot.application.agent.tools import ToolContext
from interview_copilot.domain.coaching import (
    CoachingDecision,
    CoachingMode,
    CoachingTaskPlan,
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
        result = await self._graph.ainvoke(
            CoachState(
                operation="plan",
                mode=mode,
                user_data=user_data,
                tool_context=ToolContext(
                    user_id=user_id, request_id=request_id, session_id=session_id
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
        self._validate_assessment_evidence(decision, str(user_data.get("用户回答", "")))
        return decision

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
        instructions = self._instructions(
            skill,
            "生成一项可在 5 至 30 分钟内完成的训练任务。"
            "根据需要调用检索工具，dimensions 只能使用评价标准中的 key。",
        )
        task = await self._client.run_json(
            instructions=instructions,
            user_data=state["user_data"],
            context=state["tool_context"],
            allowed_tools=_RETRIEVAL_TOOLS,
            output_model=CoachingTaskPlan,
            max_tool_calls=3,
        )
        self._validate_dimensions(task.dimensions, skill)
        return {"task": task}

    async def _evaluate_answer(self, state: CoachState) -> CoachState:
        skill = state["skill"]
        instructions = self._instructions(
            skill,
            "评价用户本轮回答并决定 follow_up、retry 或 complete。"
            "只评价训练任务 dimensions 指定的维度。"
            "evidence_quote 必须逐字复制用户回答中的连续原句，不得改写、纠错或引用资料。"
            "每个 assessment 都必须返回 level 和 evidence_quote：observed 使用 1 至 5 和原句，"
            "evidence_insufficient 两项都使用 null。"
            "若这是最后一轮，action 必须为 complete。",
        )
        decision = await self._client.run_json(
            instructions=instructions,
            user_data=state["user_data"],
            context=state["tool_context"],
            allowed_tools=set(),
            output_model=CoachingDecision,
            max_tool_calls=0,
        )
        self._validate_dimensions([item.key for item in decision.assessments], skill)
        task = state["user_data"].get("训练任务")
        if isinstance(task, dict):
            selected = task.get("dimensions")
            if isinstance(selected, list):
                unexpected = {item.key for item in decision.assessments}.difference(
                    str(item) for item in selected
                )
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
    def _validate_assessment_evidence(decision: CoachingDecision, answer: str) -> None:
        for assessment in decision.assessments:
            if assessment.evidence_quote and assessment.evidence_quote not in answer:
                raise DeepSeekAgentError(f"评价维度 {assessment.key} 引用了回答中不存在的证据")

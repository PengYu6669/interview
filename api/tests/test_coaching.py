from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.api import coaching as coaching_api
from interview_copilot.api.coaching import create_coaching_speech_ticket
from interview_copilot.application.agent.skills import ActivatedSkill, SkillMetadata
from interview_copilot.application.coaching import CoachingService
from interview_copilot.application.coaching_protocol import (
    normalize_task_plan,
    resolve_exercise,
)
from interview_copilot.domain.coaching import (
    CoachingAttemptComparison,
    CoachingComparisonItem,
    CoachingDecision,
    CoachingNextPractice,
    CoachingPriorityGap,
    CoachingTaskPlan,
    DimensionAssessment,
)
from interview_copilot.infrastructure.database import Base, UserRecord


class FakeCoach:
    model_name = "fake-model"
    prompt_version = "fake-coach-v1"

    def __init__(self) -> None:
        self.evaluate_calls = 0

    async def plan(self, **_: object) -> tuple[ActivatedSkill, CoachingTaskPlan]:
        return (
            ActivatedSkill(
                metadata=SkillMetadata(
                    name="structured-expression-coach",
                    version="1.0.0",
                    title="结构化表达训练",
                    description="测试",
                    training_mode="structured_expression",
                ),
                instructions="测试训练",
                rubric={"dimensions": [{"key": "conclusion"}]},
            ),
            CoachingTaskPlan(
                title="项目表达",
                objective="说明个人贡献",
                scenario="面试官要求介绍项目。",
                primary_question="请说明你在项目中的核心贡献。",
                estimated_minutes=10,
                dimensions=["conclusion", "ownership"],
            ),
        )

    async def evaluate(self, **_: object) -> CoachingDecision:
        self.evaluate_calls += 1
        complete = self.evaluate_calls > 1
        return CoachingDecision(
            action="complete" if complete else "retry",
            coach_reply="已收到回答。",
            next_question=None if complete else "请重新说明你在项目中的核心贡献。",
            assessments=[
                DimensionAssessment(
                    key="conclusion",
                    status="evidence_insufficient",
                    level=None,
                    evidence_quote=None,
                    feedback="还需要更直接的结论。",
                    confidence=0.4,
                )
            ],
            summary="继续补充个人贡献。" if not complete else "本次训练完成。",
            priority_gaps=[] if complete else [
                CoachingPriorityGap(
                    dimension="ownership",
                    diagnosis="个人职责不够具体。",
                    retry_prompt="用一句话说清你独立负责的范围。",
                )
            ],
            comparison=(
                CoachingAttemptComparison(
                    items=[
                        CoachingComparisonItem(
                            dimension="ownership",
                            change="improved",
                            before_level=2,
                            after_level=4,
                            before_quote="我负责检索链路。",
                            after_quote="我选择混合检索并负责评测。",
                            explanation="重答补充了具体决策与职责。",
                        )
                    ],
                    overall_summary="个人贡献比首次回答更具体。",
                )
                if complete
                else None
            ),
            next_practice=(
                CoachingNextPractice(
                    focus="继续练习方案取舍",
                    recommended_difficulty="assisted",
                )
                if complete
                else None
            ),
        )


def _user(session: Session, name: str) -> UserRecord:
    record = UserRecord(
        username=name,
        email=f"{name}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
    )
    session.add(record)
    session.commit()
    return record


@pytest.mark.asyncio
async def test_coaching_session_requires_start_is_idempotent_and_completes() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "coach-owner")
        stranger = _user(session, "coach-stranger")
        coach = FakeCoach()
        service = CoachingService(session, coach)
        created = await service.create(
            user_id=owner.id,
            request_id=uuid4(),
            mode="structured_expression",
            channel="text",
            target_role="AI 应用开发工程师",
            training_goal="练习项目表达",
            source_ids=[],
        )

        assert created.status == "planned"
        assert created.current_question == "请说明你在项目中的核心贡献。"
        with pytest.raises(ValueError, match="不能提交"):
            await service.answer(
                user_id=owner.id,
                session_id=created.id,
                client_message_id=uuid4(),
                answer="我负责检索链路。",
                answer_mode="text",
            )
        service.start(user_id=owner.id, session_id=created.id)
        message_id = uuid4()
        first = await service.answer(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=message_id,
            answer="我负责检索链路。",
            answer_mode="text",
            elapsed_seconds=45,
        )
        repeated = await service.answer(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=message_id,
            answer="重复请求不会再次评价。",
            answer_mode="text",
        )
        completed = await service.answer(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=uuid4(),
            answer="我选择混合检索并负责评测。",
            answer_mode="text",
        )

        assert len(first.turns) == 1
        assert first.turns[0].attempt_number == 1
        assert first.turns[0].elapsed_seconds == 45
        assert first.turns[0].decision.delivery_metrics is not None
        assert first.turns[0].decision.delivery_metrics.character_count == len("我负责检索链路。")
        assert len(repeated.turns) == 1
        assert coach.evaluate_calls == 2
        assert completed.status == "completed"
        assert completed.current_question is None
        with pytest.raises(LookupError):
            service.get(user_id=stranger.id, session_id=created.id)


def test_dimension_assessment_requires_real_evidence_shape() -> None:
    with pytest.raises(ValueError, match="必须包含"):
        DimensionAssessment(
            key="ownership",
            status="observed",
            level=3,
            evidence_quote=None,
            feedback="职责基本明确。",
            confidence=0.7,
        )


def test_comparison_change_is_derived_from_consistent_levels_and_quotes() -> None:
    comparison = CoachingComparisonItem(
        dimension="ownership",
        change="improved",
        before_level=4,
        after_level=3,
        before_quote="第一次回答",
        after_quote="第二次回答",
        explanation="模型错误地标记为进步。",
    )

    assert comparison.change == "regressed"


def test_comparison_without_double_sided_evidence_becomes_insufficient() -> None:
    comparison = CoachingComparisonItem(
        dimension="ownership",
        change="improved",
        before_level=2,
        after_level=4,
        before_quote="第一次回答",
        after_quote=None,
        explanation="缺少第二次回答原句。",
    )

    assert comparison.change == "insufficient"
    assert comparison.before_level is None
    assert comparison.after_level is None


def test_business_protocol_pins_versioned_scenario_and_progressive_hints() -> None:
    generated = CoachingTaskPlan(
        title="模型生成的标题",
        objective="训练业务决策",
        scenario="模型生成的场景",
        primary_question="模型生成的问题",
        estimated_minutes=10,
        dimensions=["business_goal", "metrics", "assumptions", "validation"],
        exercise_type="decision_simulation",
        framework="business_decision",
        difficulty="pressure",
        target_dimension="metrics",
    )

    normalized = normalize_task_plan(
        generated,
        mode="business_sense",
        exercise_type="decision_simulation",
        difficulty="pressure",
    )

    assert normalized.scenario_version == "decision-retention-2026-01"
    assert normalized.primary_question.startswith("你会如何定义问题")
    assert normalized.facts[0].source_type == "virtual"
    assert normalized.time_limit_seconds == 120
    assert normalized.puzzle is None
    assert [item.key for item in normalized.scaffold] == [
        "goal",
        "diagnosis",
        "priority",
        "guardrail",
    ]


def test_exercise_type_must_match_training_mode() -> None:
    with pytest.raises(ValueError, match="不匹配"):
        resolve_exercise("structured_expression", "fermi_estimation")


def test_coaching_speech_ticket_requires_an_owned_active_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = SimpleNamespace(id=uuid4())
    session_id = uuid4()
    monkeypatch.setattr(coaching_api.settings, "speech_ticket_secret", "x" * 32)

    active_service = SimpleNamespace(
        get=lambda **_: SimpleNamespace(status="active")
    )
    response = create_coaching_speech_ticket(session_id, user, active_service)
    assert response.ticket
    assert response.expires_at > datetime.now(UTC)

    planned_service = SimpleNamespace(
        get=lambda **_: SimpleNamespace(status="planned")
    )
    with pytest.raises(HTTPException) as not_started:
        create_coaching_speech_ticket(session_id, user, planned_service)
    assert not_started.value.status_code == 409

    def reject_access(**_: object) -> None:
        raise LookupError("找不到这项专项训练")

    with pytest.raises(HTTPException) as inaccessible:
        create_coaching_speech_ticket(
            session_id,
            user,
            SimpleNamespace(get=reject_access),
        )
    assert inaccessible.value.status_code == 404

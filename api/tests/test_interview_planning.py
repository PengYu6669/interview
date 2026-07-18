from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from interview_copilot.application.interview_planning import (
    InterviewPlanningError,
    InterviewPlanningService,
)
from interview_copilot.application.interview_runtime import InterviewRuntimeService
from interview_copilot.application.retrieval.indexing import RagIndexingService
from interview_copilot.application.retrieval.search import RagSearchService
from interview_copilot.domain.interviews import (
    InterviewInterruptionDecision,
    InterviewPhasePlan,
    InterviewPlan,
    InterviewQuestionPlan,
    InterviewTurnDecision,
)
from interview_copilot.domain.retrieval import (
    IndexedRagDocument,
    RagDocumentInput,
    RetrievedEvidence,
)
from interview_copilot.infrastructure.career import WeeklyPlanItemRecord, WeeklyPlanRecord
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.drafts import TrainingDraftRecord
from interview_copilot.infrastructure.interviews import (
    InterviewSessionRecord,  # noqa: F401
    InterviewTurnRecord,
)


class FakeGenerator:
    model_name = "fake-model"
    prompt_version = "test-v1"

    def __init__(self, minutes: tuple[int, int, int] = (10, 18, 2)) -> None:
        self._minutes = minutes
        self.last_request: dict[str, object] = {}

    async def generate(self, **kwargs: object) -> InterviewPlan:
        self.last_request = kwargs
        return InterviewPlan(
            target_role="Python 后端工程师",
            summary="重点验证项目深度与系统设计。",
            phases=[
                InterviewPhasePlan(
                    name="项目深挖",
                    kind="project",
                    minutes=self._minutes[0],
                    skills=["项目证据"],
                    questions=[
                        InterviewQuestionPlan(
                            prompt="说明你的核心贡献。",
                            intent="核实个人职责。",
                            skills=["项目证据"],
                        )
                    ],
                ),
                InterviewPhasePlan(
                    name="系统设计",
                    kind="system_design",
                    minutes=self._minutes[1],
                    skills=["容量规划"],
                    questions=[
                        InterviewQuestionPlan(
                            prompt="如何估算容量？",
                            intent="验证量化能力。",
                            skills=["容量规划"],
                        )
                    ],
                ),
                InterviewPhasePlan(
                    name="候选人反问",
                    kind="candidate_qa",
                    minutes=self._minutes[2],
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


class FakeDecider:
    model_name = "fake-model"
    prompt_version = "turn-test-v1"

    def __init__(self) -> None:
        self.calls = 0

    async def decide(self, **kwargs: object) -> InterviewTurnDecision:
        self.calls += 1
        if kwargs.get("phase_kind") == "candidate_qa":
            if "没有" in str(kwargs.get("answer", "")):
                return InterviewTurnDecision(
                    action="next",
                    rationale="候选人已完成反问",
                    transition="好的，感谢你的提问。",
                    interviewer_reply="好的，那我们结束今天的面试交流。",
                )
            return InterviewTurnDecision(
                action="follow_up",
                follow_up_question="你还有其他想了解的吗？",
                rationale="已回答候选人的问题并继续提供反问机会",
                transition="这是一个很实际的问题。",
                interviewer_reply="在这次虚拟面试设定中，岗位会关注工程质量和跨团队协作。",
            )
        if self.calls == 1:
            return InterviewTurnDecision(
                action="follow_up",
                follow_up_question="你具体负责了哪一部分？",
                rationale="个人职责不够明确",
                transition="好的，我想再了解一个具体细节。",
            )
        return InterviewTurnDecision(
            action="next",
            rationale="回答已覆盖当前考察意图",
            transition="好的，这部分我了解了。我们继续下一个问题。",
        )

    async def assess_interruption(self, **_: object) -> InterviewInterruptionDecision:
        return InterviewInterruptionDecision(
            should_interrupt=True,
            reason="vague",
            transition="先停一下，你的描述还比较宽泛。",
            follow_up_question="请直接说明你负责的核心模块和量化结果。",
            rationale="长时间回答仍缺少个人职责与证据",
        )


class FakeRagIndexing(RagIndexingService):
    def __init__(self) -> None:
        pass

    async def index(self, document: RagDocumentInput) -> IndexedRagDocument:
        return IndexedRagDocument(
            id=document.source_id or uuid4(),
            corpus_type=document.corpus_type,
            source_type=document.source_type,
            title=document.title,
            chunk_count=1,
            warnings=[],
            indexed_at=datetime.now(UTC),
        )


class FakeRagSearch(RagSearchService):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def search(self, **kwargs: object) -> list[RetrievedEvidence]:
        self.calls.append(kwargs)
        return []


def _planning_service(
    session: Session,
    generator: FakeGenerator,
    rag_search: FakeRagSearch | None = None,
) -> InterviewPlanningService:
    return InterviewPlanningService(
        session,
        generator,
        rag_indexing=FakeRagIndexing(),
        rag_search=rag_search or FakeRagSearch(),
    )


class MissingCandidateQAGenerator(FakeGenerator):
    async def generate(self, **kwargs: object) -> InterviewPlan:
        plan = await super().generate(**kwargs)
        phases = list(plan.phases[:-1])
        phases[-1] = phases[-1].model_copy(
            update={"minutes": phases[-1].minutes + plan.phases[-1].minutes}
        )
        return plan.model_copy(update={"phases": phases})


@pytest.mark.asyncio
async def test_creates_idempotent_owned_interview_plan() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _create_user(session, "owner")
        stranger = _create_user(session, "stranger")
        draft = _create_draft(session, owner.id, extraction={"schema_version": "test"})
        draft.target_company = "示例科技"
        draft.target_level = "senior"
        draft.interview_round = "second"
        draft.interview_type = "system_design"
        session.commit()
        generator = FakeGenerator()
        rag_search = FakeRagSearch()
        service = _planning_service(session, generator, rag_search)

        created = await service.create(user_id=owner.id, draft_id=draft.id)
        repeated = await service.create(user_id=owner.id, draft_id=draft.id)

        assert created.id == repeated.id
        assert created.duration_minutes == 30
        assert created.target_company == "示例科技"
        assert created.target_level == "senior"
        assert created.interview_round == "second"
        assert created.interview_type == "system_design"
        assert generator.last_request["target_company"] == "示例科技"
        assert generator.last_request["target_level"] == "senior"
        assert generator.last_request["interview_round"] == "second"
        assert generator.last_request["interview_type"] == "system_design"
        assert set(generator.last_request["rag_context"]) == {  # type: ignore[arg-type]
            "candidate",
            "job",
            "knowledge",
        }
        assert [call["corpus_types"] for call in rag_search.calls] == [
            ["candidate"],
            ["job"],
            ["knowledge"],
        ]
        assert [phase.name for phase in created.phases] == [
            "项目深挖",
            "系统设计",
            "候选人反问",
        ]
        assert created.phases[-1].kind == "candidate_qa"
        assert all(not hasattr(phase, "questions") for phase in created.phases)
        runtime = service.start(user_id=owner.id, session_id=created.id)
        assert runtime.status == "started"
        assert runtime.current_question == "说明你的核心贡献。"
        assert runtime.current_question_number == 1
        assert runtime.current_question_kind == "main"
        assert "林老师" in runtime.opening_statement
        assert runtime.total_questions == 3
        assert 29 * 60 <= runtime.remaining_seconds <= 30 * 60
        progress_before_pause = (
            runtime.current_phase_index,
            runtime.current_question_number,
            runtime.current_question,
        )
        paused = service.pause(user_id=owner.id, session_id=created.id)
        assert paused.status == "paused"
        assert paused.remaining_seconds <= runtime.remaining_seconds
        resumed = service.start(user_id=owner.id, session_id=created.id)
        assert resumed.status == "started"
        assert (
            resumed.current_phase_index,
            resumed.current_question_number,
            resumed.current_question,
        ) == progress_before_pause
        ended = service.end(user_id=owner.id, session_id=created.id)
        assert ended.status == "ended"
        assert ended.current_question is None
        assert ended.answered_questions == 0
        with pytest.raises(ValueError, match="不能结束"):
            service.end(user_id=owner.id, session_id=created.id)
        with pytest.raises(LookupError):
            service.get(user_id=stranger.id, session_id=created.id)


@pytest.mark.asyncio
async def test_existing_plan_is_available_without_configured_generator() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _create_user(session, "owner")
        draft = _create_draft(session, owner.id, extraction={"schema_version": "test"})
        created = await _planning_service(session, FakeGenerator()).create(
            user_id=owner.id,
            draft_id=draft.id,
        )

        restored = await InterviewPlanningService(session).create(
            user_id=owner.id,
            draft_id=draft.id,
        )

        assert restored.id == created.id


@pytest.mark.asyncio
async def test_new_plan_requires_configured_generator() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _create_user(session, "owner")
        draft = _create_draft(session, owner.id, extraction={"schema_version": "test"})

        with pytest.raises(InterviewPlanningError, match="DEEPSEEK_API_KEY"):
            await InterviewPlanningService(session).create(
                user_id=owner.id,
                draft_id=draft.id,
            )


@pytest.mark.asyncio
async def test_rejects_missing_extraction_and_invalid_total_duration() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _create_user(session, "owner")
        missing = _create_draft(session, owner.id, extraction=None)
        service = _planning_service(session, FakeGenerator())
        with pytest.raises(ValueError, match="结构化提取"):
            await service.create(user_id=owner.id, draft_id=missing.id)

        invalid = _create_draft(session, owner.id, extraction={"schema_version": "test"})
        invalid.duration_minutes = 40
        session.commit()
        with pytest.raises(InterviewPlanningError, match="总时长"):
            await service.create(user_id=owner.id, draft_id=invalid.id)

        missing_qa = _create_draft(session, owner.id, extraction={"schema_version": "test"})
        with pytest.raises(InterviewPlanningError, match="最终反问阶段"):
            await _planning_service(session, MissingCandidateQAGenerator()).create(
                user_id=owner.id,
                draft_id=missing_qa.id,
            )


@pytest.mark.asyncio
async def test_persists_idempotent_answers_and_advances_questions() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _create_user(session, "owner")
        now = datetime.now(UTC)
        weekly_plan = WeeklyPlanRecord(
            user_id=owner.id,
            week_start=date(2026, 7, 13),
            goal="完成模拟面试",
            status="active",
            basis={},
            confirmed_at=now,
            created_at=now,
            updated_at=now,
        )
        plan_item = WeeklyPlanItemRecord(
            plan=weekly_plan,
            scheduled_date=date(2026, 7, 17),
            estimated_minutes=30,
            task_type="mock_interview",
            title="项目深挖模拟面试",
            reason="验证项目表达",
            completion_criteria="完成整场面试",
            status="pending",
            origin="ai",
            position=0,
            created_at=now,
            updated_at=now,
        )
        session.add(weekly_plan)
        session.flush()
        draft = _create_draft(session, owner.id, extraction={"schema_version": "test"})
        draft.career_plan_item_id = plan_item.id
        session.commit()
        planning = _planning_service(session, FakeGenerator())
        created = await planning.create(user_id=owner.id, draft_id=draft.id)
        planning.start(user_id=owner.id, session_id=created.id)
        session.refresh(plan_item)
        assert plan_item.status == "in_progress"
        decider = FakeDecider()
        runtime = InterviewRuntimeService(session, decider)

        message_id = uuid4()
        followed_up = await runtime.answer(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=message_id,
            answer="我负责服务端开发。",
            answer_mode="text",
        )
        duplicate = await runtime.answer(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=message_id,
            answer="这次重试不应再次保存。",
            answer_mode="text",
        )

        assert followed_up.current_question == "你具体负责了哪一部分？"
        assert followed_up.current_question_number == 1
        assert followed_up.current_question_kind == "follow_up"
        assert followed_up.follow_up_count == 1
        assert followed_up.interviewer_transition == "好的，我想再了解一个具体细节。"
        assert duplicate.current_question == followed_up.current_question
        assert decider.calls == 1
        assert session.query(InterviewTurnRecord).count() == 1

        advanced = await runtime.answer(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=uuid4(),
            answer="我实现了鉴权和数据库写入，并负责上线验证。",
            answer_mode="text",
        )
        assert advanced.current_question == "如何估算容量？"
        assert advanced.answered_questions == 1
        assert advanced.current_question_number == 2
        assert advanced.current_question_kind == "main"

        candidate_qa = await runtime.answer(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=uuid4(),
            answer="容量按峰值 QPS、响应大小和冗余系数估算。",
            answer_mode="text",
        )
        assert candidate_qa.current_question == "你有什么想了解的吗？"
        assert candidate_qa.phases[candidate_qa.current_phase_index].kind == "candidate_qa"

        interview_record = session.get(InterviewSessionRecord, created.id)
        assert interview_record
        interview_record.pressure_level = 5
        session.commit()
        calls_before_interruption = decider.calls
        interrupted, unchanged = await runtime.interrupt(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=uuid4(),
            partial_answer="我想了解岗位的工程质量要求，以及团队通常如何进行跨团队协作和技术方案评审。",
            elapsed_seconds=20,
        )
        assert interrupted is False
        assert unchanged.current_question == candidate_qa.current_question
        assert decider.calls == calls_before_interruption

        replied = await runtime.answer(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=uuid4(),
            answer="这个岗位平时最关注哪些工程能力？",
            answer_mode="voice",
        )
        assert replied.current_question == "你还有其他想了解的吗？"
        assert replied.interviewer_reply and "虚拟面试设定" in replied.interviewer_reply
        latest_turn = session.scalar(
            select(InterviewTurnRecord).order_by(InterviewTurnRecord.sequence.desc()).limit(1)
        )
        assert latest_turn and latest_turn.interviewer_reply == replied.interviewer_reply

        completed = await runtime.answer(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=uuid4(),
            answer="没有其他问题了，谢谢。",
            answer_mode="voice",
        )
        assert completed.status == "completed"
        assert completed.interviewer_reply == "好的，那我们结束今天的面试交流。"
        assert completed.closing_statement and "复盘报告" in completed.closing_statement
        persisted_session = session.get(InterviewSessionRecord, created.id)
        assert persisted_session and persisted_session.status == "completed"
        assert persisted_session.completed_at is not None
        session.refresh(plan_item)
        assert plan_item.status == "completed"
        assert weekly_plan.status == "completed"
        assert session.query(InterviewTurnRecord).count() == 5
        calls_after_completion = decider.calls
        with pytest.raises(ValueError, match="不能提交回答"):
            await runtime.answer(
                user_id=owner.id,
                session_id=created.id,
                client_message_id=uuid4(),
                answer="完成后不应再次保存。",
                answer_mode="text",
            )
        assert decider.calls == calls_after_completion


@pytest.mark.asyncio
async def test_high_pressure_interruption_becomes_persisted_turn() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _create_user(session, "pressure-owner")
        draft = _create_draft(session, owner.id, extraction={"schema_version": "test"})
        draft.pressure_level = 5
        session.commit()
        planning = _planning_service(session, FakeGenerator())
        created = await planning.create(user_id=owner.id, draft_id=draft.id)
        planning.start(user_id=owner.id, session_id=created.id)
        runtime = InterviewRuntimeService(session, FakeDecider())

        interrupted, result = await runtime.interrupt(
            user_id=owner.id,
            session_id=created.id,
            client_message_id=uuid4(),
            partial_answer="我主要参与了项目开发，做了很多性能优化和稳定性工作，但是具体来说涉及的内容比较多。",
            elapsed_seconds=20,
        )

        assert interrupted is True
        assert result.current_question_kind == "follow_up"
        assert result.current_question == "请直接说明你负责的核心模块和量化结果。"
        turn = session.query(InterviewTurnRecord).one()
        assert turn.answer_mode == "voice"
        assert turn.transition == "先停一下，你的描述还比较宽泛。"


def _create_user(session: Session, name: str) -> UserRecord:
    user = UserRecord(
        username=name,
        email=f"{name}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.flush()
    return user


def _create_draft(
    session: Session, user_id: UUID, *, extraction: dict | None
) -> TrainingDraftRecord:
    now = datetime.now(UTC)
    draft = TrainingDraftRecord(
        user_id=user_id,
        resume_filename="resume.md",
        resume_text="负责 Python 服务开发。",
        jd="需要系统设计经验。",
        target_role="Python 后端工程师",
        mode="normal",
        duration_minutes=30,
        extraction=extraction,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(days=7),
    )
    session.add(draft)
    session.commit()
    return draft

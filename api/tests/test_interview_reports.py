from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from interview_copilot.application.claim_verification import ClaimVerificationError
from interview_copilot.application.interview_reports import (
    InterviewReportError,
    InterviewReportInProgressError,
    InterviewReportReviewError,
    InterviewReportService,
)
from interview_copilot.domain.coding import CodingProblemSpec, CodingTestCase
from interview_copilot.domain.interviews import (
    InterviewPhasePlan,
    InterviewPlan,
    InterviewQuestionPlan,
    InterviewReportContent,
    InterviewReportFinding,
    InterviewReportReviewOutcome,
    InterviewReportReviewRequest,
    InterviewSkillScore,
)
from interview_copilot.infrastructure.boards import InterviewBoardSnapshotRecord
from interview_copilot.infrastructure.coding import (
    InterviewCodingRunRecord,
    InterviewCodingSnapshotRecord,
)
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.drafts import TrainingDraftRecord  # noqa: F401
from interview_copilot.infrastructure.interviews import (
    InterviewReportRecord,  # noqa: F401
    InterviewReportReviewRecord,
    InterviewSessionRecord,
    InterviewTurnRecord,
)
from interview_copilot.infrastructure.questions import QuestionRecord  # noqa: F401


class FakeReportGenerator:
    model_name = "fake-report-model"
    prompt_version = "report-test-v1"
    rubric_version = "rubric-test-v1"

    def __init__(self, *, valid_quote: bool = True, fail: bool = False) -> None:
        self.valid_quote = valid_quote
        self.fail = fail
        self.calls = 0
        self.last_request: dict[str, object] = {}

    async def generate(self, **kwargs: object) -> InterviewReportContent:
        self.calls += 1
        self.last_request = kwargs
        if self.fail:
            raise InterviewReportError("报告服务暂时不可用")
        quote = "我负责接口鉴权" if self.valid_quote else "这句原话并不存在"
        return InterviewReportContent(
            overall_score=68,
            evidence_coverage=35,
            confidence=0.55,
            summary="本场中途结束，报告只覆盖已回答内容。",
            strengths=[
                InterviewReportFinding(
                    skill="项目职责",
                    title="能够说明个人负责范围",
                    evidence_turns=[1],
                    evidence_quote=quote,
                    analysis="回答明确提到了本人负责的模块。",
                )
            ],
            improvements=[
                InterviewReportFinding(
                    skill="量化表达",
                    title="缺少结果指标",
                    evidence_turns=[1],
                    evidence_quote=quote,
                    analysis="当前证据没有覆盖优化前后的指标。",
                    improvement="补充基线、结果和测量方法。",
                )
            ],
            skill_scores=[
                InterviewSkillScore(
                    skill="项目职责",
                    score=68,
                    confidence=0.55,
                    evidence_turns=[1],
                )
            ],
            next_training="针对个人贡献和量化结果进行项目深挖训练。",
        )


class FakeReportReviewer:
    model_name = "fake-review-model"
    prompt_version = "report-review-test-v1"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def review(self, **_: object) -> InterviewReportReviewOutcome:
        self.calls += 1
        if self.fail:
            raise InterviewReportReviewError("复核模型暂时不可用")
        return InterviewReportReviewOutcome(
            decision="revised",
            rationale="原评分没有充分考虑回答中明确的职责证据。",
            revised_score=74,
            confidence=0.72,
        )


class FailingClaimVerifier:
    async def verify(self, **_: object) -> list:
        raise ClaimVerificationError("权威知识检索暂时不可用")


@pytest.mark.asyncio
async def test_history_and_idempotent_evidence_report() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = _user(session, "report-owner")
        interview = _interview(session, user.id, status="ended")
        _turn(session, interview.id)
        generator = FakeReportGenerator()
        service = InterviewReportService(session, generator)

        history = service.history(user_id=user.id)
        pending_status = service.generation_status(user_id=user.id, session_id=interview.id)
        first = await service.generate(user_id=user.id, session_id=interview.id)
        repeated = await service.generate(user_id=user.id, session_id=interview.id)

        assert len(history) == 1
        assert history[0].turn_count == 1
        assert history[0].status == "ended"
        assert history[0].report_status == "not_started"
        assert history[0].report_summary is None
        assert pending_status.status == "not_started"
        assert first.content.evidence_coverage == 35
        assert first.turn_count == 1
        assert first.turns[0].sequence == 1
        assert first.turns[0].phase_name == "项目深挖"
        assert first.turns[0].question_number == 1
        assert first.turns[0].question == "请说明你的个人贡献。"
        assert first.turns[0].answer == "我负责接口鉴权，但没有记录具体性能指标。"
        assert first.turns[0].answer_mode == "voice"
        assert repeated.created_at == first.created_at
        assert first.target_level == "campus"
        assert first.interview_round == "first"
        assert first.interview_type == "comprehensive"
        assert generator.calls == 1
        reviewed = service.history(user_id=user.id)[0]
        assert reviewed.report_available is True
        assert reviewed.report_summary == "本场中途结束，报告只覆盖已回答内容。"
        assert reviewed.evidence_update == "改进 · 量化表达：缺少结果指标"
        assert service.generation_status(user_id=user.id, session_id=interview.id).status == "ready"


@pytest.mark.asyncio
async def test_report_persists_board_and_coding_evidence() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = _user(session, "report-board-owner")
        interview = _interview(session, user.id, status="ended")
        _turn(session, interview.id)
        plan = InterviewPlan.model_validate(interview.plan)
        problem = CodingProblemSpec(
            title="两数之和",
            description="返回目标下标。",
            starter_code="def solve(nums, target):\n    pass\n",
            public_tests=[
                CodingTestCase(name="样例", arguments=[[2, 7], 9], expected=[0, 1])
            ],
        )
        coding_question = plan.phases[0].questions[0].model_copy(
            update={"coding_spec": problem}
        )
        coding_phase = plan.phases[0].model_copy(
            update={"kind": "coding", "questions": [coding_question]}
        )
        interview.plan = plan.model_copy(
            update={"phases": [coding_phase, plan.phases[1]]}
        ).model_dump(mode="json")
        node_id = uuid4()
        coding_snapshot = InterviewCodingSnapshotRecord(
            session_id=interview.id,
            user_id=user.id,
            phase_index=0,
            question_index=0,
            revision=0,
            client_snapshot_id=uuid4(),
            source="def solve(nums, target):\n    return [0, 1]\n",
            complexity_notes="时间 O(n)，空间 O(n)。",
            created_at=datetime.now(UTC),
        )
        session.add(coding_snapshot)
        session.flush()
        session.add_all([
            InterviewBoardSnapshotRecord(
                session_id=interview.id,
                user_id=user.id,
                revision=0,
                client_snapshot_id=uuid4(),
                state={
                    "nodes": [
                        {
                            "id": str(node_id),
                            "kind": "service",
                            "label": "鉴权服务",
                            "x": 80,
                            "y": 80,
                            "width": 180,
                            "height": 72,
                        }
                    ],
                    "edges": [],
                    "annotations": [],
                },
                created_at=datetime.now(UTC),
            ),
            InterviewCodingRunRecord(
                session_id=interview.id,
                user_id=user.id,
                snapshot_id=coding_snapshot.id,
                client_request_id=uuid4(),
                status="passed",
                tests=[{"name": "样例", "passed": True}],
                duration_ms=18,
                error=None,
                created_at=datetime.now(UTC),
            ),
        ])
        session.commit()

        generator = FakeReportGenerator()
        report = await InterviewReportService(session, generator).generate(
            user_id=user.id,
            session_id=interview.id,
        )

        assert report.board_snapshot is not None
        assert report.board_snapshot.revision == 0
        assert report.board_snapshot.state.nodes[0].label == "鉴权服务"
        assert generator.last_request["board_snapshot"] is not None
        assert len(report.coding_evidence) == 1
        assert report.coding_evidence[0].snapshot_count == 1
        assert report.coding_evidence[0].runs[0].passed_count == 1
        assert generator.last_request["coding_evidence"][0].latest_source.startswith("def solve")


@pytest.mark.asyncio
async def test_report_rejects_active_session_and_fabricated_quote() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = _user(session, "invalid-report")
        active = _interview(session, user.id, status="started")
        _turn(session, active.id)
        with pytest.raises(ValueError, match="已完成或已结束"):
            await InterviewReportService(session, FakeReportGenerator()).generate(
                user_id=user.id,
                session_id=active.id,
            )

        active.status = "ended"
        active.completed_at = datetime.now(UTC)
        session.commit()
        with pytest.raises(InterviewReportError, match="原话"):
            await InterviewReportService(
                session,
                FakeReportGenerator(valid_quote=False),
            ).generate(user_id=user.id, session_id=active.id)


@pytest.mark.asyncio
async def test_report_generation_records_verification_degradation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = _user(session, "verification-degraded-owner")
        interview = _interview(session, user.id, status="ended")
        _turn(session, interview.id)
        generator = FakeReportGenerator()
        service = InterviewReportService(session, generator, FailingClaimVerifier())

        report = await service.generate(user_id=user.id, session_id=interview.id)

        assert report.verification_status == "degraded"
        assert report.verification_error == "权威知识检索暂时不可用"
        assert report.verified_claims == []
        assert generator.last_request["verification_status"] == "degraded"


@pytest.mark.asyncio
async def test_report_generation_lock_failure_and_stale_retry() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = _user(session, "report-retry")
        interview = _interview(session, user.id, status="ended")
        _turn(session, interview.id)
        interview.report_status = "generating"
        interview.report_generation_id = uuid4()
        interview.report_generation_started_at = datetime.now(UTC)
        session.commit()

        blocked_generator = FakeReportGenerator()
        with pytest.raises(InterviewReportInProgressError, match="正在生成"):
            await InterviewReportService(session, blocked_generator).generate(
                user_id=user.id,
                session_id=interview.id,
            )
        assert blocked_generator.calls == 0

        interview.report_generation_started_at = datetime.now(UTC) - timedelta(minutes=4)
        session.commit()
        failing_generator = FakeReportGenerator(fail=True)
        with pytest.raises(InterviewReportError, match="暂时不可用"):
            await InterviewReportService(session, failing_generator).generate(
                user_id=user.id,
                session_id=interview.id,
            )
        failed = InterviewReportService(session).generation_status(
            user_id=user.id,
            session_id=interview.id,
        )
        assert failed.status == "failed"
        assert failed.message == "报告服务暂时不可用"

        recovered_generator = FakeReportGenerator()
        recovered = await InterviewReportService(session, recovered_generator).generate(
            user_id=user.id,
            session_id=interview.id,
        )
        assert recovered.content.overall_score == 68
        assert recovered_generator.calls == 1
        assert interview.report_status == "ready"


@pytest.mark.asyncio
async def test_report_review_is_idempotent_and_keeps_original_report() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = _user(session, "review-owner")
        interview = _interview(session, user.id, status="ended")
        _turn(session, interview.id)
        service = InterviewReportService(session, FakeReportGenerator())
        original = await service.generate(user_id=user.id, session_id=interview.id)
        reviewer = FakeReportReviewer()
        request = InterviewReportReviewRequest(
            client_request_id=uuid4(),
            skill_index=0,
            action="reevaluate",
            reason="这段回答已经明确说明了个人职责，希望重新核对评分。",
        )

        first = await service.review(
            user_id=user.id,
            session_id=interview.id,
            request=request,
            reviewer=reviewer,
        )
        repeated = await service.review(
            user_id=user.id,
            session_id=interview.id,
            request=request,
            reviewer=reviewer,
        )
        refreshed = service.get(user_id=user.id, session_id=interview.id)

        assert first.id == repeated.id
        assert first.decision == "revised"
        assert first.revised_score == 74
        assert reviewer.calls == 1
        assert refreshed.content.skill_scores[0].score == original.content.skill_scores[0].score
        assert refreshed.reviews[0].id == first.id


@pytest.mark.asyncio
async def test_report_review_exclusion_and_failure_are_persisted() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = _user(session, "review-failure-owner")
        interview = _interview(session, user.id, status="ended")
        _turn(session, interview.id)
        service = InterviewReportService(session, FakeReportGenerator())
        await service.generate(user_id=user.id, session_id=interview.id)

        excluded = await service.review(
            user_id=user.id,
            session_id=interview.id,
            request=InterviewReportReviewRequest(
                client_request_id=uuid4(),
                skill_index=0,
                action="exclude",
                reason="这次回答被环境中断，不希望它进入长期能力画像。",
            ),
            reviewer=None,
        )
        assert excluded.decision == "excluded"
        assert excluded.model is None

        with pytest.raises(InterviewReportReviewError, match="暂时不可用"):
            await service.review(
                user_id=user.id,
                session_id=interview.id,
                request=InterviewReportReviewRequest(
                    client_request_id=uuid4(),
                    skill_index=0,
                    action="reevaluate",
                    reason="评分没有覆盖我回答里的职责证据，请重新检查。",
                ),
                reviewer=FakeReportReviewer(fail=True),
            )
        failed = session.scalar(
            select(InterviewReportReviewRecord).where(
                InterviewReportReviewRecord.status == "failed"
            )
        )
        assert failed is not None
        assert failed.rationale == "复核模型暂时不可用"

        with pytest.raises(ValueError, match="评分不存在"):
            await service.review(
                user_id=user.id,
                session_id=interview.id,
                request=InterviewReportReviewRequest(
                    client_request_id=uuid4(),
                    skill_index=1,
                    action="exclude",
                    reason="这个能力并没有在本次面试中被真正考察。",
                ),
                reviewer=None,
            )

        other = _user(session, "review-other-owner")
        with pytest.raises(LookupError, match="没有可复核的报告"):
            await service.review(
                user_id=other.id,
                session_id=interview.id,
                request=InterviewReportReviewRequest(
                    client_request_id=uuid4(),
                    skill_index=0,
                    action="exclude",
                    reason="其他账号不能操作这份不属于自己的面试报告。",
                ),
                reviewer=None,
            )


def test_report_review_request_rejects_blank_reason() -> None:
    with pytest.raises(ValueError, match="至少需要 10 个字"):
        InterviewReportReviewRequest(
            client_request_id=uuid4(),
            skill_index=0,
            action="exclude",
            reason="          ",
        )


def _user(session: Session, username: str) -> UserRecord:
    user = UserRecord(
        username=username,
        email=f"{username}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.flush()
    return user


def _interview(session: Session, user_id, *, status: str) -> InterviewSessionRecord:
    plan = InterviewPlan(
        target_role="Python 后端工程师",
        summary="项目深挖训练",
        phases=[
            InterviewPhasePlan(
                name="项目深挖",
                minutes=15,
                skills=["项目职责"],
                questions=[
                    InterviewQuestionPlan(
                        prompt="请说明你的个人贡献。",
                        intent="核实职责",
                        skills=["项目职责"],
                    )
                ],
            ),
            InterviewPhasePlan(
                name="系统设计",
                minutes=15,
                skills=["系统设计"],
                questions=[
                    InterviewQuestionPlan(
                        prompt="请设计一个鉴权系统。",
                        intent="考察设计能力",
                        skills=["系统设计"],
                    )
                ],
            ),
        ],
    )
    now = datetime.now(UTC)
    record = InterviewSessionRecord(
        user_id=user_id,
        draft_id=uuid4(),
        status=status,
        target_role=plan.target_role,
        mode="normal",
        duration_minutes=30,
        pressure_level=3,
        depth_level=4,
        guidance_level=3,
        summary=plan.summary,
        plan=plan.model_dump(mode="json"),
        model="fake-model",
        prompt_version="plan-test-v1",
        current_phase_index=0,
        current_question_index=0,
        created_at=now,
        started_at=now,
        completed_at=now if status == "ended" else None,
        active_question="请说明你的个人贡献。",
        follow_up_count=0,
    )
    session.add(record)
    session.commit()
    return record


def _turn(session: Session, session_id) -> None:
    session.add(
        InterviewTurnRecord(
            session_id=session_id,
            client_message_id=uuid4(),
            sequence=1,
            phase_index=0,
            question_index=0,
            question="请说明你的个人贡献。",
            answer="我负责接口鉴权，但没有记录具体性能指标。",
            answer_mode="voice",
            decision="next",
            rationale="已覆盖职责",
            transition="好的，我们继续。",
            follow_up_question=None,
            model="fake-model",
            prompt_version="turn-test-v1",
            created_at=datetime.now(UTC),
        )
    )
    session.commit()

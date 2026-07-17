from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.ability_profile import AbilityProfileService
from interview_copilot.domain.coaching import (
    CoachingDecision,
    CoachingTaskPlan,
    DimensionAssessment,
)
from interview_copilot.domain.interviews import (
    InterviewReportContent,
    InterviewReportFinding,
    InterviewSkillScore,
)
from interview_copilot.infrastructure.career import WeeklyPlanItemRecord  # noqa: F401
from interview_copilot.infrastructure.coaching import (
    CoachingSessionRecord,
    CoachingTurnRecord,
)
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.drafts import TrainingDraftRecord  # noqa: F401
from interview_copilot.infrastructure.interviews import (
    InterviewReportRecord,
    InterviewReportReviewRecord,
)
from interview_copilot.infrastructure.questions import QuestionRecord  # noqa: F401


def test_builds_kline_and_weighted_skill_matrix_from_reports() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = UserRecord(
            username="profile-owner",
            email="profile@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        session.flush()
        first_time = datetime.now(UTC) - timedelta(days=3)
        _report(session, user.id, first_time, overall=60, skill_score=55, coverage=40)
        _report(session, user.id, datetime.now(UTC), overall=72, skill_score=75, coverage=80)
        session.commit()

        profile = AbilityProfileService(session).get(user_id=user.id)

        assert profile.report_count == 2
        assert profile.average_score == 66
        assert profile.average_coverage == 60
        assert [point.close for point in profile.kline] == [60, 72]
        assert profile.kline[1].open == 60
        assert profile.kline[1].high == 75
        assert profile.skills[0].skill == "系统设计"
        assert profile.skills[0].trend == 20
        assert 55 < profile.skills[0].score < 75
        assert profile.skills[0].training_focus == "补充流量基线和容量计算。"
        assert profile.skills[0].evidence_quote == "我根据流量做了扩容"
        assert profile.skills[0].source_session_id == profile.kline[-1].session_id
        assert profile.next_training == "练习容量估算和故障降级。"


def test_empty_profile_does_not_invent_scores() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user_id = uuid4()
        profile = AbilityProfileService(session).get(user_id=user_id)

        assert profile.report_count == 0
        assert profile.average_score is None
        assert profile.kline == []
        assert profile.skills == []
        assert profile.coaching.session_count == 0


def test_profile_applies_latest_review_without_mutating_report_history() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = UserRecord(
            username="reviewed-profile-owner",
            email="reviewed-profile@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        session.flush()
        first = _report(
            session,
            user.id,
            datetime.now(UTC) - timedelta(days=3),
            overall=60,
            skill_score=55,
            coverage=60,
        )
        second = _report(
            session,
            user.id,
            datetime.now(UTC),
            overall=72,
            skill_score=75,
            coverage=80,
        )
        session.flush()
        session.add_all(
            [
                _review(first, user.id, action="reevaluate", decision="revised", score=70),
                _review(second, user.id, action="exclude", decision="excluded", score=None),
            ]
        )
        session.commit()

        profile = AbilityProfileService(session).get(user_id=user.id)

        assert [point.close for point in profile.kline] == [60, 72]
        assert profile.skills[0].score == 70
        assert profile.skills[0].report_count == 1
        assert profile.skills[0].source_session_id == first.session_id
        assert profile.next_training == "练习容量估算和故障降级。"
        assert InterviewReportContent.model_validate(second.content).skill_scores[0].score == 75


def test_profile_does_not_recommend_a_fully_excluded_report() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = UserRecord(
            username="fully-excluded-owner",
            email="fully-excluded@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        session.flush()
        report = _report(
            session,
            user.id,
            datetime.now(UTC),
            overall=40,
            skill_score=35,
            coverage=20,
        )
        session.flush()
        session.add(
            _review(report, user.id, action="exclude", decision="excluded", score=None)
        )
        session.commit()

        profile = AbilityProfileService(session).get(user_id=user.id)

        assert profile.skills == []
        assert profile.next_training is None


def test_profile_treats_uncertain_review_as_insufficient_evidence() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = UserRecord(
            username="uncertain-review-owner",
            email="uncertain-review@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        session.flush()
        report = _report(
            session,
            user.id,
            datetime.now(UTC),
            overall=10,
            skill_score=10,
            coverage=5,
        )
        session.flush()
        session.add(
            _review(report, user.id, action="reevaluate", decision="uncertain", score=None)
        )
        session.commit()

        profile = AbilityProfileService(session).get(user_id=user.id)

        assert profile.report_count == 1
        assert profile.skills == []
        assert profile.next_training is None


def test_profile_keeps_specialized_training_evidence_separate_from_kline() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = UserRecord(
            username="coaching-profile-owner",
            email="coaching-profile@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        session.flush()
        coaching = CoachingSessionRecord(
            user_id=user.id,
            mode="structured_expression",
            channel="text",
            status="completed",
            target_role="AI 应用开发工程师",
            training_goal="练习结论先行",
            skill_name="structured-expression-coach",
            skill_version="1.0.0",
            task=CoachingTaskPlan(
                title="项目表达",
                objective="说明项目价值",
                scenario="项目面试",
                primary_question="请介绍项目。",
                estimated_minutes=10,
                dimensions=["conclusion", "ownership"],
            ).model_dump(mode="json"),
            current_question=None,
            source_ids=[],
            model="fake-model",
            prompt_version="fake-prompt-v1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.add(coaching)
        session.flush()
        decision = CoachingDecision(
            action="complete",
            coach_reply="本轮完成。",
            next_question=None,
            assessments=[
                DimensionAssessment(
                    key="conclusion",
                    status="observed",
                    level=4,
                    evidence_quote="我先说结论。",
                    feedback="结论清楚，可以补充量化结果。",
                    confidence=0.8,
                )
            ],
            summary="结论先行表现稳定。",
        )
        session.add(
            CoachingTurnRecord(
                session_id=coaching.id,
                client_message_id=uuid4(),
                sequence=1,
                answer="我先说结论。",
                answer_mode="text",
                decision=decision.model_dump(mode="json"),
                model="fake-model",
                prompt_version="fake-prompt-v1",
                created_at=datetime.now(UTC),
            )
        )
        session.commit()

        profile = AbilityProfileService(session).get(user_id=user.id)

        assert profile.report_count == 0
        assert profile.kline == []
        assert profile.coaching.session_count == 1
        assert profile.coaching.completed_count == 1
        assert profile.coaching.skills[0].dimension == "conclusion"
        assert profile.coaching.skills[0].score == 80
        assert profile.coaching.next_mode == "structured_expression"


def test_coaching_mastery_requires_three_independent_strong_sessions() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = UserRecord(
            username="mastery-owner",
            email="mastery@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add(user)
        session.flush()
        for offset in (2, 1, 0):
            completed_at = datetime.now(UTC) - timedelta(days=offset)
            coaching = CoachingSessionRecord(
                user_id=user.id,
                mode="structured_expression",
                channel="voice",
                status="completed",
                target_role="后端工程师",
                training_goal="练习结论先行",
                skill_name="structured-expression-coach",
                skill_version="2.0.0",
                task=CoachingTaskPlan(
                    title="项目表达",
                    objective="先说结论",
                    scenario="技术面试",
                    primary_question="请介绍项目。",
                    estimated_minutes=10,
                    dimensions=["conclusion", "ownership"],
                ).model_dump(mode="json"),
                current_question=None,
                source_ids=[],
                model="fake-model",
                prompt_version="fake-prompt-v2",
                created_at=completed_at,
                updated_at=completed_at,
                completed_at=completed_at,
            )
            session.add(coaching)
            session.flush()
            decision = CoachingDecision(
                action="complete",
                coach_reply="回答完成。",
                next_question=None,
                assessments=[
                    DimensionAssessment(
                        key="conclusion",
                        status="observed",
                        level=4,
                        evidence_quote="我的结论是采用渐进迁移。",
                        feedback="结论明确。",
                        confidence=0.8,
                    )
                ],
                summary="结论稳定。",
            )
            session.add(
                CoachingTurnRecord(
                    session_id=coaching.id,
                    client_message_id=uuid4(),
                    sequence=2,
                    answer="我的结论是采用渐进迁移。",
                    answer_mode="voice",
                    attempt_number=2,
                    elapsed_seconds=60,
                    decision=decision.model_dump(mode="json"),
                    model="fake-model",
                    prompt_version="fake-prompt-v2",
                    created_at=completed_at,
                )
            )
        session.commit()

        profile = AbilityProfileService(session).get(user_id=user.id)

        assert profile.coaching.skills[0].mastery_status == "stable"
        assert profile.coaching.skills[0].session_count == 3
        assert profile.coaching.current_streak_days == 3
        assert profile.coaching.next_difficulty == "pressure"


def _report(
    session: Session,
    user_id,
    created_at: datetime,
    *,
    overall: int,
    skill_score: int,
    coverage: int,
) -> InterviewReportRecord:
    finding = InterviewReportFinding(
        skill="系统设计",
        title="容量规划需要补充",
        evidence_turns=[1],
        evidence_quote="我根据流量做了扩容",
        analysis="缺少量化过程。",
        improvement="补充流量基线和容量计算。",
    )
    content = InterviewReportContent(
        overall_score=overall,
        evidence_coverage=coverage,
        confidence=coverage / 100,
        summary="只评价已有回答。",
        strengths=[],
        improvements=[finding],
        skill_scores=[
            InterviewSkillScore(
                skill="系统设计",
                score=skill_score,
                confidence=coverage / 100,
                evidence_turns=[1],
            )
        ],
        next_training="练习容量估算和故障降级。",
    )
    record = InterviewReportRecord(
        session_id=uuid4(),
        user_id=user_id,
        content=content.model_dump(mode="json"),
        model="fake-model",
        prompt_version="report-test-v1",
        rubric_version="rubric-test-v1",
        created_at=created_at,
    )
    session.add(record)
    return record


def _review(
    report: InterviewReportRecord,
    user_id,
    *,
    action: str,
    decision: str,
    score: int | None,
) -> InterviewReportReviewRecord:
    now = datetime.now(UTC)
    return InterviewReportReviewRecord(
        report_id=report.id,
        session_id=report.session_id,
        user_id=user_id,
        client_request_id=uuid4(),
        skill_index=0,
        skill="系统设计",
        original_score=55,
        action=action,
        reason="用户认为本次评分需要重新核对。",
        status="resolved",
        decision=decision,
        rationale="已根据原回答证据完成处理。",
        revised_score=score,
        confidence=0.8,
        model="fake-review-model" if action == "reevaluate" else None,
        prompt_version="report-review-test-v1" if action == "reevaluate" else None,
        created_at=now,
        resolved_at=now,
    )

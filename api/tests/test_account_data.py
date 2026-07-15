from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from interview_copilot.application.account_data import AccountDataService, CurrentPasswordError
from interview_copilot.application.authentication import AuthenticationService
from interview_copilot.infrastructure.database import AuthSessionRecord, Base, UserRecord
from interview_copilot.infrastructure.drafts import TrainingDraftQuestionRecord, TrainingDraftRecord
from interview_copilot.infrastructure.interviews import (
    InterviewReportRecord,
    InterviewReportReviewRecord,
    InterviewSessionRecord,
    InterviewTurnRecord,
)
from interview_copilot.infrastructure.questions import (
    QuestionConversationRecord,
    QuestionMessageRecord,
    QuestionRecord,
    UserQuestionNoteRecord,
    UserQuestionProgressRecord,
)


@pytest.fixture
def database() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


def seed_account_data(session: Session) -> tuple[UserRecord, UserRecord, TrainingDraftRecord]:
    auth = AuthenticationService(session, session_days=7)
    owner_id = auth.register(username="owner", email="owner@example.com", password="123456").user.id
    other_id = auth.register(username="other", email="other@example.com", password="123456").user.id
    now = datetime.now(UTC)
    owner = session.get(UserRecord, owner_id)
    other = session.get(UserRecord, other_id)
    assert owner and other
    private_question = QuestionRecord(
        slug="owner-question",
        title="私有问题",
        prompt="请说明你的项目职责",
        difficulty="medium",
        question_type="project",
        intent="核验个人贡献",
        answer_outline=["职责", "行动", "结果"],
        common_mistakes=["只说团队"],
        published=False,
        created_at=now,
        owner_user_id=owner.id,
        content_markdown="# 私有问题",
        source_document_name="个人题库.md",
    )
    session.add(private_question)
    session.flush()
    draft = TrainingDraftRecord(
        user_id=owner.id,
        resume_filename="简历.pdf",
        resume_text="包含敏感但属于用户本人的简历原文",
        jd="后端工程师",
        target_role="后端工程师",
        mode="normal",
        duration_minutes=20,
        pressure_level=3,
        depth_level=4,
        guidance_level=2,
        training_focus="项目贡献",
        extraction={"skills": ["Python"]},
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(days=7),
    )
    session.add(draft)
    session.flush()
    session.add(TrainingDraftQuestionRecord(draft_id=draft.id, question_id=private_question.id))
    interview = InterviewSessionRecord(
        user_id=owner.id,
        draft_id=draft.id,
        status="ended",
        target_role="后端工程师",
        mode="normal",
        duration_minutes=20,
        pressure_level=3,
        depth_level=4,
        guidance_level=2,
        training_focus="项目贡献",
        summary="项目深挖",
        plan={"phases": []},
        model="deepseek-v4-flash",
        prompt_version="interview-plan-v1",
        created_at=now,
        started_at=now,
        completed_at=now,
    )
    session.add(interview)
    session.flush()
    session.add(
        InterviewTurnRecord(
            session_id=interview.id,
            client_message_id=uuid4(),
            sequence=1,
            phase_index=0,
            question_index=0,
            question="你的职责是什么？",
            answer="我负责核心接口设计。",
            answer_mode="voice",
            decision="next",
            rationale="证据充分",
            transition="明白了。",
            follow_up_question=None,
            model="deepseek-v4-flash",
            prompt_version="interview-turn-v1",
            created_at=now,
        )
    )
    report = InterviewReportRecord(
        session_id=interview.id,
        user_id=owner.id,
        content={"summary": "只评价已有回答"},
        model="deepseek-v4-flash",
        prompt_version="interview-report-v1",
        rubric_version="technical-interview-rubric-v1",
        created_at=now,
    )
    session.add(report)
    session.flush()
    session.add(
        InterviewReportReviewRecord(
            report_id=report.id,
            session_id=interview.id,
            user_id=owner.id,
            client_request_id=uuid4(),
            skill_index=0,
            skill="项目职责",
            original_score=60,
            action="exclude",
            reason="这次回答被打断，不希望计入长期能力画像。",
            status="resolved",
            decision="excluded",
            rationale="已从能力画像聚合中排除。",
            revised_score=None,
            confidence=1.0,
            model=None,
            prompt_version=None,
            created_at=now,
            resolved_at=now,
        )
    )
    session.add(
        UserQuestionProgressRecord(
            user_id=owner.id,
            question_id=private_question.id,
            status="learning",
            bookmarked=True,
            updated_at=now,
        )
    )
    session.add(
        UserQuestionNoteRecord(
            user_id=owner.id,
            question_id=private_question.id,
            content="需要补充量化结果",
            updated_at=now,
        )
    )
    conversation = QuestionConversationRecord(
        user_id=owner.id, question_id=private_question.id, created_at=now
    )
    session.add(conversation)
    session.flush()
    session.add(
        QuestionMessageRecord(
            conversation_id=conversation.id,
            role="user",
            content="如何回答？",
            citations=[],
            created_at=now,
        )
    )
    session.commit()
    return owner, other, draft


def test_summary_and_export_only_include_current_users_data(database: Session) -> None:
    owner, other, draft = seed_account_data(database)
    service = AccountDataService(database)

    summary = service.summary(user_id=owner.id)
    exported = service.export(user_id=owner.id)

    assert summary.draft_count == 1
    assert summary.interview_count == 1
    assert summary.report_count == 1
    assert summary.private_question_count == 1
    assert exported.training_drafts[0].id == draft.id
    assert exported.interview_sessions[0].turns[0].answer == "我负责核心接口设计。"
    assert exported.format_version == "account-export-v2"
    assert exported.interview_sessions[0].report is not None
    assert exported.interview_sessions[0].report.reviews[0].decision == "excluded"
    assert exported.learning_states[0].note == "需要补充量化结果"
    assert exported.question_conversations[0].messages[0].content == "如何回答？"
    assert exported.account.id == owner.id
    assert exported.account.id != other.id
    payload = exported.model_dump(mode="json")
    assert "password_hash" not in str(payload)
    assert "session_token" not in str(payload)


def test_delete_requires_current_password_and_preserves_data_on_failure(database: Session) -> None:
    owner, _, _ = seed_account_data(database)
    service = AccountDataService(database)

    with pytest.raises(CurrentPasswordError, match="当前密码不正确"):
        service.delete_account(user_id=owner.id, current_password="wrong")

    assert database.get(UserRecord, owner.id) is not None
    assert service.summary(user_id=owner.id).interview_count == 1


def test_delete_removes_owned_data_without_touching_other_account(database: Session) -> None:
    owner, other, _ = seed_account_data(database)
    service = AccountDataService(database)

    service.delete_account(user_id=owner.id, current_password="123456")

    assert database.get(UserRecord, owner.id) is None
    assert database.get(UserRecord, other.id) is not None
    assert (
        database.scalar(
            select(InterviewSessionRecord).where(InterviewSessionRecord.user_id == owner.id)
        )
        is None
    )
    assert database.scalar(select(InterviewTurnRecord)) is None
    assert database.scalar(select(InterviewReportReviewRecord)) is None
    assert (
        database.scalar(select(TrainingDraftRecord).where(TrainingDraftRecord.user_id == owner.id))
        is None
    )
    assert (
        database.scalar(select(QuestionRecord).where(QuestionRecord.owner_user_id == owner.id))
        is None
    )
    assert (
        database.scalar(
            select(UserQuestionProgressRecord).where(UserQuestionProgressRecord.user_id == owner.id)
        )
        is None
    )
    assert (
        database.scalar(
            select(UserQuestionNoteRecord).where(UserQuestionNoteRecord.user_id == owner.id)
        )
        is None
    )
    assert (
        database.scalar(
            select(QuestionConversationRecord).where(QuestionConversationRecord.user_id == owner.id)
        )
        is None
    )
    assert (
        database.scalar(select(AuthSessionRecord).where(AuthSessionRecord.user_id == owner.id))
        is None
    )

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.drafts import DraftLockedError, DraftService
from interview_copilot.infrastructure.career import WeeklyPlanItemRecord, WeeklyPlanRecord
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.interviews import InterviewSessionRecord
from interview_copilot.infrastructure.questions import QuestionRecord


def test_draft_accepts_public_and_owned_questions_but_rejects_private_foreign_question() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "draft-owner")
        other = _user(session, "draft-other")
        public = _question(session, "public-question", published=True, owner_user_id=None)
        owned = _question(session, "owned-question", published=False, owner_user_id=owner.id)
        foreign = _question(session, "foreign-question", published=False, owner_user_id=other.id)
        session.commit()
        service = DraftService(session, retention_days=7)

        draft = service.create(
            user_id=owner.id,
            data=_draft_data([public.id, owned.id]),
        )

        assert set(draft.question_ids) == {public.id, owned.id}
        assert draft.target_company == "示例科技"
        assert draft.target_level == "senior"
        assert draft.interview_round == "second"
        assert draft.interview_type == "system_design"
        updated = service.update(
            user_id=owner.id,
            draft_id=draft.id,
            data={"target_role": "资深 Python 工程师", "question_ids": [owned.id]},
        )
        assert updated.target_role == "资深 Python 工程师"
        assert updated.question_ids == [owned.id]
        with pytest.raises(ValueError, match="无权"):
            service.create(user_id=owner.id, data=_draft_data([foreign.id]))

        session.add(
            InterviewSessionRecord(
                user_id=owner.id,
                draft_id=draft.id,
                status="planned",
                target_role=updated.target_role,
                mode="normal",
                duration_minutes=30,
                summary="测试计划",
                plan={"target_role": updated.target_role, "summary": "测试计划", "phases": []},
                model="fake-model",
                prompt_version="test-v1",
                current_phase_index=0,
                current_question_index=0,
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
        with pytest.raises(DraftLockedError, match="新的训练版本"):
            service.update(
                user_id=owner.id,
                draft_id=draft.id,
                data={"target_role": "再次修改的岗位"},
            )


def test_draft_retraining_source_requires_owned_ready_report() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "retraining-owner")
        other = _user(session, "retraining-other")
        service = DraftService(session, retention_days=7)
        owner_source_draft = service.create(user_id=owner.id, data=_draft_data([]))
        other_source_draft = service.create(user_id=other.id, data=_draft_data([]))
        owner_source = _interview(
            session,
            user_id=owner.id,
            draft_id=owner_source_draft.id,
            report_status="ready",
        )
        other_source = _interview(
            session,
            user_id=other.id,
            draft_id=other_source_draft.id,
            report_status="ready",
        )
        pending_source_draft = service.create(user_id=owner.id, data=_draft_data([]))
        pending_source = _interview(
            session,
            user_id=owner.id,
            draft_id=pending_source_draft.id,
            report_status="not_started",
        )
        session.commit()

        accepted = service.create(
            user_id=owner.id,
            data={**_draft_data([]), "source_session_id": owner_source.id},
        )
        assert accepted.source_session_id == owner_source.id

        for invalid_source_id in (other_source.id, pending_source.id):
            with pytest.raises(ValueError, match="来源训练不存在"):
                service.create(
                    user_id=owner.id,
                    data={**_draft_data([]), "source_session_id": invalid_source_id},
                )


def test_list_resumable_drafts_excludes_other_users_and_consumed_drafts() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "draft-list-owner")
        other = _user(session, "draft-list-other")
        service = DraftService(session, retention_days=7)
        resumable = service.create(user_id=owner.id, data=_draft_data([]))
        consumed = service.create(user_id=owner.id, data=_draft_data([]))
        service.create(user_id=other.id, data=_draft_data([]))
        _interview(
            session,
            user_id=owner.id,
            draft_id=consumed.id,
            report_status="not_started",
        )
        session.commit()

        summaries = service.list_resumable(user_id=owner.id)

        assert [item.id for item in summaries] == [resumable.id]
        assert summaries[0].resume_filename == "resume.md"


def test_draft_mock_plan_link_requires_owned_active_item() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "plan-draft-owner")
        other = _user(session, "plan-draft-other")
        owned_item = _plan_item(session, owner.id)
        foreign_item = _plan_item(session, other.id)
        session.commit()
        service = DraftService(session, retention_days=7)

        accepted = service.create(
            user_id=owner.id,
            data={**_draft_data([]), "career_plan_item_id": owned_item.id},
        )
        assert accepted.career_plan_item_id == owned_item.id

        with pytest.raises(ValueError, match="模拟面试计划项不存在"):
            service.create(
                user_id=owner.id,
                data={**_draft_data([]), "career_plan_item_id": foreign_item.id},
            )


def _user(session: Session, name: str) -> UserRecord:
    record = UserRecord(
        username=name,
        email=f"{name}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
    )
    session.add(record)
    session.flush()
    return record


def _interview(
    session: Session,
    *,
    user_id,
    draft_id,
    report_status: str,
) -> InterviewSessionRecord:
    record = InterviewSessionRecord(
        user_id=user_id,
        draft_id=draft_id,
        status="completed",
        target_role="Python 后端工程师",
        mode="normal",
        duration_minutes=30,
        summary="测试计划",
        plan={"target_role": "Python 后端工程师", "summary": "测试计划", "phases": []},
        model="fake-model",
        prompt_version="test-v1",
        current_phase_index=0,
        current_question_index=0,
        report_status=report_status,
        created_at=datetime.now(UTC),
    )
    session.add(record)
    session.flush()
    return record


def _plan_item(session: Session, user_id) -> WeeklyPlanItemRecord:
    now = datetime.now(UTC)
    plan = WeeklyPlanRecord(
        user_id=user_id,
        week_start=date(2026, 7, 13),
        goal="完成模拟面试",
        status="active",
        basis={},
        confirmed_at=now,
        created_at=now,
        updated_at=now,
    )
    item = WeeklyPlanItemRecord(
        plan=plan,
        scheduled_date=date(2026, 7, 17),
        estimated_minutes=30,
        task_type="mock_interview",
        title="模拟面试",
        reason="验证薄弱能力",
        completion_criteria="完成整场面试",
        status="pending",
        origin="ai",
        position=0,
        created_at=now,
        updated_at=now,
    )
    session.add(plan)
    session.flush()
    return item


def _question(
    session: Session,
    slug: str,
    *,
    published: bool,
    owner_user_id,
) -> QuestionRecord:
    record = QuestionRecord(
        slug=slug,
        title=slug,
        prompt="请说明实现方案。",
        difficulty="进阶",
        question_type="技术题",
        intent="考察实现能力",
        answer_outline=["方案", "取舍"],
        common_mistakes=["缺少证据"],
        published=published,
        created_at=datetime.now(UTC),
        owner_user_id=owner_user_id,
        content_markdown="# 参考内容",
        source_document_name=None,
    )
    session.add(record)
    session.flush()
    return record


def _draft_data(question_ids: list) -> dict:
    return {
        "resume_filename": "resume.md",
        "resume_text": "负责 FastAPI 项目开发。",
        "jd": "负责后端系统设计、性能优化与可靠性建设。",
        "target_role": "Python 后端工程师",
        "target_company": "示例科技",
        "target_level": "senior",
        "interview_round": "second",
        "interview_type": "system_design",
        "mode": "normal",
        "duration_minutes": 30,
        "pressure_level": 3,
        "depth_level": 4,
        "guidance_level": 3,
        "question_ids": question_ids,
    }

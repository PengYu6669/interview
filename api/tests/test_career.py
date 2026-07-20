from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.agent.career_planner import (
    CareerPlanAgentItem,
    CareerPlanAgentOutput,
    CareerProfileAgentOutput,
)
from interview_copilot.application.agent.skills import ActivatedSkill, SkillMetadata
from interview_copilot.application.career import CareerService
from interview_copilot.domain.career import CareerProfile, WeeklyPlanItem
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.drafts import TrainingDraftRecord  # noqa: F401
from interview_copilot.infrastructure.questions import QuestionRecord
from interview_copilot.providers.deepseek_agent import DeepSeekAgentError


class FakePlanner:
    model_name = "fake-planner"
    prompt_version = "career-planning-test-v1"

    def __init__(self, question_id: UUID) -> None:
        self.question_id = question_id
        self.last_user_data: dict[str, object] = {}

    async def plan(self, **kwargs: object) -> tuple[ActivatedSkill, CareerPlanAgentOutput]:
        user_data = kwargs.get("user_data")
        if isinstance(user_data, dict):
            self.last_user_data = user_data
        return (
            ActivatedSkill(
                metadata=SkillMetadata(
                    name="career-planning-coach",
                    version="1.1.0",
                    title="求职训练规划",
                    description="测试规划",
                    training_mode="career_planning",
                ),
                instructions="测试",
                rubric={"version": "career-planning-rubric-v1.1"},
            ),
            CareerPlanAgentOutput(
                goal="练清项目表达",
                items=[
                    CareerPlanAgentItem(
                        day_index=0,
                        time_slot="evening",
                        estimated_minutes=20,
                        task_type="question_review",
                        title="项目 STAR 重答",
                        reason="个人题库与目标岗位相关",
                        completion_criteria="完成两次回答，背景不超过两句话",
                        question_id=self.question_id,
                        question_count=2,
                        coaching_mode=None,
                        exercise_type=None,
                        difficulty=None,
                    )
                ],
            ),
        )

    async def profile_from_message(self, **_: object) -> CareerProfileAgentOutput:
        return CareerProfileAgentOutput(
            reply="已记录目标岗位和本周时间。",
            ready=True,
            target_role="前端工程师",
            weekly_hours=8,
            available_weekdays=[1, 3, 5],
        )


class DuplicateQuestionPlanner(FakePlanner):
    async def plan(self, **_: object) -> tuple[ActivatedSkill, CareerPlanAgentOutput]:
        skill, output = await super().plan()
        duplicate = output.items[0].model_copy(
            update={"day_index": 2, "title": "同一题再次训练"}
        )
        return skill, output.model_copy(update={"items": [output.items[0], duplicate]})


def _user(session: Session, name: str) -> UserRecord:
    user = UserRecord(
        username=name,
        email=f"{name}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def _question(session: Session, owner: UserRecord) -> QuestionRecord:
    record = QuestionRecord(
        slug=f"career-{uuid4().hex}",
        title="介绍一次模型性能优化经历",
        prompt="请使用 STAR 说明你如何优化模型性能。",
        difficulty="intermediate",
        question_type="project",
        intent="考察项目表达",
        answer_outline=["背景", "行动", "结果"],
        common_mistakes=["背景过长"],
        published=False,
        owner_user_id=owner.id,
        content_markdown="",
        framework="star",
        created_at=datetime.now(UTC),
    )
    session.add(record)
    session.commit()
    return record


@pytest.mark.asyncio
async def test_plan_draft_requires_confirmation_and_updates_owned_item() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "career-owner")
        stranger = _user(session, "career-stranger")
        question = _question(session, owner)
        planner = FakePlanner(question.id)
        service = CareerService(session, planner)
        service.save_profile(
            user_id=owner.id,
            profile=CareerProfile(
                target_role="AI 应用开发工程师",
                target_level="中级",
                weekly_hours=2,
                available_weekdays=[0, 2],
            ),
        )

        draft = await service.create_draft(
            user_id=owner.id,
            request_id=uuid4(),
            week_start=date(2026, 7, 13),
            instruction="周三没时间，增加周六训练",
        )
        assert service.get(user_id=owner.id).weekly_plan is None
        assert draft.items[0].question_id == question.id
        assert draft.items[0].title.startswith("精练 2 道")
        assert draft.items[0].completion_criteria.startswith("精练 2 道")
        assert planner.last_user_data["用户本轮调整要求"] == "周三没时间，增加周六训练"

        await service.create_draft(
            user_id=owner.id,
            request_id=uuid4(),
            week_start=date(2026, 7, 13),
            instruction="把周二任务移到周三，其他不变",
        )
        assert planner.last_user_data["当前计划"] is not None

        plan = service.save_weekly_plan(
            user_id=owner.id,
            week_start=draft.week_start,
            goal=draft.goal,
            items=draft.items,
            status="active",
            draft_id=draft.id,
        )
        await service.create_draft(
            user_id=owner.id,
            request_id=uuid4(),
            week_start=date(2026, 7, 13),
            instruction="增加周六训练，其他不变",
        )
        assert planner.last_user_data["当前计划"]["id"] == str(plan.id)
        completed = service.update_item_status(
            user_id=owner.id,
            plan_id=plan.id,
            item_id=plan.items[0].id,
            status="completed",
        )

        assert completed.status == "completed"
        assert service.get(user_id=owner.id).weekly_plan is not None
        with pytest.raises(LookupError, match="找不到这项训练计划"):
            service.update_item_status(
                user_id=stranger.id,
                plan_id=plan.id,
                item_id=plan.items[0].id,
                status="completed",
            )


@pytest.mark.asyncio
async def test_planner_rejects_unapproved_question_uuid() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "allowlist-owner")
        service = CareerService(session, FakePlanner(uuid4()))
        service.save_profile(
            user_id=owner.id,
            profile=CareerProfile(target_role="后端开发", available_weekdays=[0]),
        )
        with pytest.raises(DeepSeekAgentError, match="未授权题目"):
            await service.create_draft(
                user_id=owner.id,
                request_id=uuid4(),
                week_start=date(2026, 7, 13),
            )


@pytest.mark.asyncio
async def test_planner_replaces_duplicate_question_with_general_review_when_needed() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "duplicate-question-owner")
        question = _question(session, owner)
        service = CareerService(session, DuplicateQuestionPlanner(question.id))
        service.save_profile(
            user_id=owner.id,
            profile=CareerProfile(target_role="后端开发", available_weekdays=[0, 2]),
        )

        draft = await service.create_draft(
            user_id=owner.id,
            request_id=uuid4(),
            week_start=date(2026, 7, 13),
        )

        assert [item.question_id for item in draft.items] == [question.id, None]
        assert draft.items[1].title == "复盘本周回答并提炼表达模板"


def test_weekly_plan_requires_monday_before_persistence() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "plan-owner")
        item = WeeklyPlanItem(
            id=uuid4(),
            scheduled_date=date(2026, 7, 16),
            task_type="question_review",
            title="训练",
            reason="手动安排",
            completion_criteria="完成一次",
        )
        with pytest.raises(ValueError, match="必须是周一"):
            CareerService(session).save_weekly_plan(
                user_id=owner.id,
                week_start=date(2026, 7, 16),
                goal="错误日期",
                items=[item],
                status="active",
            )


def test_explicit_day_move_updates_only_source_day() -> None:
    item = WeeklyPlanItem(
        id=uuid4(),
        scheduled_date=date(2026, 7, 14),
        task_type="question_review",
        title="周二任务",
        reason="手动安排",
        completion_criteria="完成一次",
    )
    moved = CareerService._apply_explicit_day_move(
        items=[item],
        instruction="把周二训练移到周三，其他安排不变",
        week_start=date(2026, 7, 13),
    )
    assert moved[0].scheduled_date == date(2026, 7, 15)


def test_training_mix_scales_mock_interviews_and_question_sessions() -> None:
    short = CareerService._training_mix(2)
    full = CareerService._training_mix(8)

    assert "安排 1 次" in str(short["题目精练"])
    assert "不安排完整模拟" in str(short["模拟面试"])
    assert "安排 3 次" in str(full["题目精练"])
    assert "至少安排 2 场" in str(full["模拟面试"])


@pytest.mark.asyncio
async def test_profile_can_be_confirmed_from_conversation() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "conversation-owner")
        planner = FakePlanner(uuid4())
        result = await CareerService(session, planner).save_profile_from_message(
            user_id=owner.id,
            request_id=uuid4(),
            message="目标前端工程师，每周八小时，周二四六训练",
        )

        assert result.profile is not None
        assert result.profile.target_role == "前端工程师"
        assert result.profile.available_weekdays == [1, 3, 5]

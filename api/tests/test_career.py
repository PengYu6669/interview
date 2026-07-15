from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.career import CareerService
from interview_copilot.domain.career import CareerProfile, WeeklyPlanItem
from interview_copilot.infrastructure.database import Base, UserRecord


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


def test_career_memory_requires_explicit_save_and_plan_is_owner_scoped() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "career-owner")
        stranger = _user(session, "career-stranger")
        service = CareerService(session)

        empty = service.get(user_id=owner.id, suggested_focus="练习量化结果")
        assert empty.profile.confirmed_at is None
        assert empty.suggested_focus == "练习量化结果"

        profile = service.save_profile(
            user_id=owner.id,
            profile=CareerProfile(
                target_role="AI 应用开发工程师",
                target_level="中级",
                weekly_hours=8,
            ),
        )
        plan = service.save_weekly_plan(
            user_id=owner.id,
            week_start=date(2026, 7, 13),
            goal="补齐项目表达",
            items=[
                WeeklyPlanItem(
                    id=uuid4(),
                    category="learning",
                    title="完成 STAR 重答",
                    target_count=3,
                    completed_count=1,
                )
            ],
            status="active",
        )

        assert profile.confirmed_at is not None
        assert service.get(user_id=owner.id, suggested_focus=None).weekly_plan == plan
        with pytest.raises(LookupError, match="找不到这份周计划"):
            service.delete_weekly_plan(user_id=stranger.id, plan_id=plan.id)
        assert service.get(user_id=stranger.id, suggested_focus=None).profile.confirmed_at is None


def test_weekly_plan_requires_monday() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "plan-owner")
        with pytest.raises(ValueError, match="必须是周一"):
            CareerService(session).save_weekly_plan(
                user_id=owner.id,
                week_start=date(2026, 7, 16),
                goal="错误日期",
                items=[
                    WeeklyPlanItem(
                        id=uuid4(), category="learning", title="训练", target_count=1
                    )
                ],
                status="active",
            )

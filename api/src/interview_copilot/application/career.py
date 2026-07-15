from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from interview_copilot.domain.career import (
    CareerProfile,
    CareerWorkspace,
    WeeklyPlan,
    WeeklyPlanItem,
)
from interview_copilot.infrastructure.career import CareerProfileRecord, WeeklyPlanRecord


class CareerService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, user_id: UUID, suggested_focus: str | None) -> CareerWorkspace:
        profile = self._session.get(CareerProfileRecord, user_id)
        plan = self._session.scalar(
            select(WeeklyPlanRecord)
            .where(WeeklyPlanRecord.user_id == user_id)
            .order_by(WeeklyPlanRecord.week_start.desc())
            .limit(1)
        )
        return CareerWorkspace(
            profile=self._profile(profile),
            weekly_plan=self._plan(plan) if plan else None,
            suggested_focus=suggested_focus,
        )

    def save_profile(self, *, user_id: UUID, profile: CareerProfile) -> CareerProfile:
        now = datetime.now(UTC)
        record = self._session.get(CareerProfileRecord, user_id)
        if not record:
            record = CareerProfileRecord(
                user_id=user_id,
                confirmed_at=now,
                updated_at=now,
            )
            self._session.add(record)
        for key, value in profile.model_dump(
            exclude={"confirmed_at", "updated_at"}, mode="python"
        ).items():
            setattr(record, key, value)
        record.confirmed_at = now
        record.updated_at = now
        self._session.commit()
        self._session.refresh(record)
        return self._profile(record)

    def delete_profile(self, *, user_id: UUID) -> None:
        self._session.execute(
            delete(CareerProfileRecord).where(CareerProfileRecord.user_id == user_id)
        )
        self._session.commit()

    def save_weekly_plan(
        self,
        *,
        user_id: UUID,
        week_start: date,
        goal: str,
        items: list[WeeklyPlanItem],
        status: str,
    ) -> WeeklyPlan:
        if week_start.weekday() != 0:
            raise ValueError("周计划开始日期必须是周一")
        now = datetime.now(UTC)
        record = self._session.scalar(
            select(WeeklyPlanRecord).where(
                WeeklyPlanRecord.user_id == user_id,
                WeeklyPlanRecord.week_start == week_start,
            )
        )
        if not record:
            record = WeeklyPlanRecord(
                id=uuid4(),
                user_id=user_id,
                week_start=week_start,
                created_at=now,
                updated_at=now,
            )
            self._session.add(record)
        record.goal = goal
        record.items = [item.model_dump(mode="json") for item in items]
        record.status = status
        record.updated_at = now
        self._session.commit()
        self._session.refresh(record)
        return self._plan(record)

    def delete_weekly_plan(self, *, user_id: UUID, plan_id: UUID) -> None:
        record = self._session.scalar(
            select(WeeklyPlanRecord).where(
                WeeklyPlanRecord.id == plan_id,
                WeeklyPlanRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到这份周计划")
        self._session.delete(record)
        self._session.commit()

    @staticmethod
    def _profile(record: CareerProfileRecord | None) -> CareerProfile:
        if not record:
            return CareerProfile()
        return CareerProfile(
            target_role=record.target_role,
            target_level=record.target_level,
            target_companies=list(record.target_companies),
            preferred_cities=list(record.preferred_cities),
            weekly_hours=record.weekly_hours,
            constraints=record.constraints,
            confirmed_at=record.confirmed_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _plan(record: WeeklyPlanRecord) -> WeeklyPlan:
        return WeeklyPlan(
            id=record.id,
            week_start=record.week_start,
            goal=record.goal,
            items=[WeeklyPlanItem.model_validate(item) for item in record.items],
            status=record.status,  # type: ignore[arg-type]
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

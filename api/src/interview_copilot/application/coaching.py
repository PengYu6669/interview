from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from interview_copilot.application.agent.skills import ActivatedSkill
from interview_copilot.domain.coaching import (
    CoachingChannel,
    CoachingDecision,
    CoachingMode,
    CoachingSessionData,
    CoachingSessionSummary,
    CoachingTaskPlan,
    CoachingTurnData,
)
from interview_copilot.infrastructure.coaching import CoachingSessionRecord, CoachingTurnRecord

MAX_COACHING_TURNS = 5


class TrainingCoach(Protocol):
    model_name: str
    prompt_version: str

    async def plan(
        self,
        *,
        mode: CoachingMode,
        user_data: dict[str, object],
        user_id: UUID,
        request_id: UUID,
        session_id: UUID | None = None,
    ) -> tuple[ActivatedSkill, CoachingTaskPlan]: ...

    async def evaluate(
        self,
        *,
        mode: CoachingMode,
        user_data: dict[str, object],
        user_id: UUID,
        request_id: UUID,
        final_turn: bool,
        session_id: UUID | None = None,
    ) -> CoachingDecision: ...


class CoachingService:
    def __init__(self, session: Session, coach: TrainingCoach | None = None) -> None:
        self._session = session
        self._coach = coach

    async def create(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        mode: CoachingMode,
        channel: CoachingChannel,
        target_role: str,
        training_goal: str,
        source_ids: list[UUID],
    ) -> CoachingSessionData:
        coach = self._required_coach()
        session_id = uuid4()
        skill, task = await coach.plan(
            mode=mode,
            user_data={
                "训练模式": mode,
                "交互形式": channel,
                "目标岗位": target_role,
                "训练目标": training_goal,
                "允许使用的资料编号": [str(item) for item in source_ids],
            },
            user_id=user_id,
            request_id=request_id,
            session_id=session_id,
        )
        now = datetime.now(UTC)
        record = CoachingSessionRecord(
            id=session_id,
            user_id=user_id,
            mode=mode,
            channel=channel,
            status="planned",
            target_role=target_role,
            training_goal=training_goal,
            skill_name=skill.metadata.name,
            skill_version=skill.metadata.version,
            task=task.model_dump(mode="json"),
            current_question=task.primary_question,
            source_ids=[str(item) for item in source_ids],
            model=coach.model_name,
            prompt_version=coach.prompt_version,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return self._to_domain(record)

    def start(self, *, user_id: UUID, session_id: UUID) -> CoachingSessionData:
        record = self._owned(user_id=user_id, session_id=session_id)
        if record.status == "completed":
            raise ValueError("这项训练已经完成")
        if record.status == "planned":
            record.status = "active"
            record.updated_at = datetime.now(UTC)
            self._session.commit()
            self._session.refresh(record)
        return self._to_domain(record)

    async def answer(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        client_message_id: UUID,
        answer: str,
        answer_mode: CoachingChannel,
    ) -> CoachingSessionData:
        duplicate = self._session.scalar(
            select(CoachingTurnRecord).where(
                CoachingTurnRecord.session_id == session_id,
                CoachingTurnRecord.client_message_id == client_message_id,
            )
        )
        if duplicate:
            return self.get(user_id=user_id, session_id=session_id)
        record = self._session.scalar(
            select(CoachingSessionRecord)
            .where(
                CoachingSessionRecord.id == session_id,
                CoachingSessionRecord.user_id == user_id,
            )
            .with_for_update()
        )
        if not record:
            raise LookupError("找不到这项专项训练")
        if record.status != "active":
            raise ValueError("这项训练当前不能提交回答")
        sequence = int(
            self._session.scalar(
                select(func.coalesce(func.max(CoachingTurnRecord.sequence), 0)).where(
                    CoachingTurnRecord.session_id == session_id
                )
            )
            or 0
        ) + 1
        history = self._turns(record.id)[-4:]
        decision = await self._required_coach().evaluate(
            mode=record.mode,  # type: ignore[arg-type]
            user_data={
                "训练任务": record.task,
                "当前问题": record.current_question,
                "用户回答": answer,
                "最近训练记录": [item.decision for item in history],
            },
            user_id=user_id,
            request_id=client_message_id,
            final_turn=sequence >= MAX_COACHING_TURNS,
            session_id=session_id,
        )
        now = datetime.now(UTC)
        self._session.add(
            CoachingTurnRecord(
                session_id=record.id,
                client_message_id=client_message_id,
                sequence=sequence,
                answer=answer,
                answer_mode=answer_mode,
                decision=decision.model_dump(mode="json"),
                model=self._required_coach().model_name,
                prompt_version=self._required_coach().prompt_version,
                created_at=now,
            )
        )
        record.current_question = decision.next_question
        record.updated_at = now
        if decision.action == "complete":
            record.status = "completed"
            record.completed_at = now
        self._session.commit()
        self._session.refresh(record)
        return self._to_domain(record)

    def get(self, *, user_id: UUID, session_id: UUID) -> CoachingSessionData:
        return self._to_domain(self._owned(user_id=user_id, session_id=session_id))

    def list_recent(self, *, user_id: UUID, limit: int = 5) -> list[CoachingSessionSummary]:
        if not 1 <= limit <= 20:
            raise ValueError("训练记录数量必须为 1 至 20")
        records = self._session.scalars(
            select(CoachingSessionRecord)
            .where(CoachingSessionRecord.user_id == user_id)
            .order_by(CoachingSessionRecord.updated_at.desc())
            .limit(limit)
        ).all()
        return [
            CoachingSessionSummary(
                id=record.id,
                mode=record.mode,  # type: ignore[arg-type]
                channel=record.channel,  # type: ignore[arg-type]
                status=record.status,  # type: ignore[arg-type]
                title=CoachingTaskPlan.model_validate(record.task).title,
                target_role=record.target_role,
                current_question=record.current_question,
                turn_count=len(self._turns(record.id)),
                updated_at=record.updated_at,
            )
            for record in records
        ]

    def _owned(self, *, user_id: UUID, session_id: UUID) -> CoachingSessionRecord:
        record = self._session.scalar(
            select(CoachingSessionRecord).where(
                CoachingSessionRecord.id == session_id,
                CoachingSessionRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到这项专项训练")
        return record

    def _turns(self, session_id: UUID) -> list[CoachingTurnRecord]:
        return list(
            self._session.scalars(
                select(CoachingTurnRecord)
                .where(CoachingTurnRecord.session_id == session_id)
                .order_by(CoachingTurnRecord.sequence)
            ).all()
        )

    def _to_domain(self, record: CoachingSessionRecord) -> CoachingSessionData:
        return CoachingSessionData(
            id=record.id,
            mode=record.mode,  # type: ignore[arg-type]
            channel=record.channel,  # type: ignore[arg-type]
            status=record.status,  # type: ignore[arg-type]
            target_role=record.target_role,
            training_goal=record.training_goal,
            skill_name=record.skill_name,
            skill_version=record.skill_version,
            task=CoachingTaskPlan.model_validate(record.task),
            current_question=record.current_question,
            turns=[
                CoachingTurnData(
                    id=turn.id,
                    sequence=turn.sequence,
                    answer=turn.answer,
                    answer_mode=turn.answer_mode,  # type: ignore[arg-type]
                    decision=CoachingDecision.model_validate(turn.decision),
                    created_at=turn.created_at,
                )
                for turn in self._turns(record.id)
            ],
            created_at=record.created_at,
            updated_at=record.updated_at,
            completed_at=record.completed_at,
        )

    def _required_coach(self) -> TrainingCoach:
        if not self._coach:
            raise RuntimeError("训练教练 Agent 尚未配置")
        return self._coach

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from interview_copilot.application.agent.skills import ActivatedSkill
from interview_copilot.application.coaching_protocol import (
    normalize_task_plan,
    resolve_exercise,
    task_protocol,
)
from interview_copilot.domain.coaching import (
    CoachingChannel,
    CoachingDecision,
    CoachingDeliveryMetrics,
    CoachingDifficulty,
    CoachingExerciseType,
    CoachingMode,
    CoachingSessionData,
    CoachingSessionSummary,
    CoachingSourceQuestion,
    CoachingTaskPlan,
    CoachingTurnData,
)
from interview_copilot.infrastructure.coaching import CoachingSessionRecord, CoachingTurnRecord
from interview_copilot.infrastructure.questions import QuestionRecord

MAX_COACHING_ATTEMPTS = 2


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
        exercise_type: CoachingExerciseType | None = None,
        difficulty: CoachingDifficulty = "guided",
    ) -> CoachingSessionData:
        coach = self._required_coach()
        sources = self._training_sources(user_id=user_id, source_ids=source_ids)
        source_questions = [
            CoachingSourceQuestion(
                id=item.id,
                title=item.title,
                prompt=item.prompt,
                framework=item.framework,  # type: ignore[arg-type]
                evidence_quotes=[evidence.quote for evidence in item.evidence[:8]],
            )
            for item in sources
        ]
        requested_exercise = exercise_type
        if mode == "structured_expression" and source_questions:
            requested_exercise = (
                "star_story" if source_questions[0].framework == "star" else "prep_pitch"
            )
        selected_exercise = resolve_exercise(mode, requested_exercise)
        session_id = uuid4()
        skill, task = await coach.plan(
            mode=mode,
            user_data={
                "训练模式": mode,
                "交互形式": channel,
                "目标岗位": target_role,
                "训练目标": training_goal,
                "允许使用的资料编号": [str(item) for item in source_ids],
                "用户选择的题目与原文证据": [
                    item.model_dump(mode="json") for item in source_questions
                ],
                **task_protocol(
                    mode=mode,
                    exercise_type=selected_exercise,
                    difficulty=difficulty,
                ),
            },
            user_id=user_id,
            request_id=request_id,
            session_id=session_id,
        )
        task = normalize_task_plan(
            task,
            mode=mode,
            exercise_type=selected_exercise,
            difficulty=difficulty,
            source_questions=source_questions,
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

    def _training_sources(
        self, *, user_id: UUID, source_ids: list[UUID]
    ) -> list[QuestionRecord]:
        unique_ids = list(dict.fromkeys(source_ids))
        if len(unique_ids) > 20:
            raise ValueError("专项训练最多选择 20 道资料题")
        if not unique_ids:
            return []
        records = self._session.scalars(
            select(QuestionRecord)
            .where(
                QuestionRecord.id.in_(unique_ids),
                or_(
                    QuestionRecord.published.is_(True),
                    QuestionRecord.owner_user_id == user_id,
                ),
            )
            .options(selectinload(QuestionRecord.evidence))
        ).all()
        by_id = {item.id: item for item in records}
        if set(by_id) != set(unique_ids):
            raise ValueError("所选专项训练资料不存在或无权使用")
        return [by_id[item] for item in unique_ids]

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
        elapsed_seconds: int | None = None,
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
        history = self._turns(record.id)
        if sequence > MAX_COACHING_ATTEMPTS:
            raise ValueError("本次双次作答训练已经完成")
        first_turn = history[0] if history else None
        decision = await self._required_coach().evaluate(
            mode=record.mode,  # type: ignore[arg-type]
            user_data={
                "训练任务": record.task,
                "当前问题": record.current_question,
                "用户回答": answer,
                "本次作答序号": sequence,
                "第一次回答": first_turn.answer if first_turn else None,
                "第一次评价": first_turn.decision if first_turn else None,
                "新增约束": (
                    record.task.get("constraint_change") if sequence == 2 else None
                ),
            },
            user_id=user_id,
            request_id=client_message_id,
            final_turn=sequence >= MAX_COACHING_ATTEMPTS,
            session_id=session_id,
        )
        decision = decision.model_copy(
            update={
                "delivery_metrics": self._delivery_metrics(
                    answer=answer,
                    answer_mode=answer_mode,
                    elapsed_seconds=elapsed_seconds,
                )
            }
        )
        self._validate_protocol_decision(decision, attempt_number=sequence)
        now = datetime.now(UTC)
        self._session.add(
            CoachingTurnRecord(
                session_id=record.id,
                client_message_id=client_message_id,
                sequence=sequence,
                answer=answer,
                answer_mode=answer_mode,
                attempt_number=sequence,
                elapsed_seconds=elapsed_seconds,
                decision=decision.model_dump(mode="json"),
                model=self._required_coach().model_name,
                prompt_version=self._required_coach().prompt_version,
                created_at=now,
            )
        )
        if sequence == 1:
            task = CoachingTaskPlan.model_validate(record.task)
            retry_focus = "；".join(item.retry_prompt for item in decision.priority_gaps)
            retry_parts = [task.primary_question, f"重答要求：{retry_focus}"]
            if task.constraint_change:
                retry_parts.append(task.constraint_change)
            record.current_question = "\n\n".join(retry_parts)
        else:
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
                title=(task := CoachingTaskPlan.model_validate(record.task)).title,
                target_role=record.target_role,
                current_question=record.current_question,
                turn_count=len(self._turns(record.id)),
                exercise_type=task.exercise_type,
                difficulty=task.difficulty,
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
                    attempt_number=turn.attempt_number,
                    elapsed_seconds=turn.elapsed_seconds,
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

    @staticmethod
    def _validate_protocol_decision(
        decision: CoachingDecision, *, attempt_number: int
    ) -> None:
        if attempt_number == 1:
            if decision.action != "retry" or not decision.next_question:
                raise ValueError("首次作答后必须保留原题进行重答")
            if decision.comparison is not None or decision.next_practice is not None:
                raise ValueError("首次作答不能提前生成训练结论")
            if not decision.priority_gaps:
                raise ValueError("首次作答必须指出一至两个优先缺口")
            return
        if decision.action != "complete" or decision.next_question is not None:
            raise ValueError("第二次作答后必须完成训练")
        if decision.comparison is None or decision.next_practice is None:
            raise ValueError("第二次作答必须返回前后对比和下一练建议")

    @staticmethod
    def _delivery_metrics(
        *, answer: str, answer_mode: CoachingChannel, elapsed_seconds: int | None
    ) -> CoachingDeliveryMetrics:
        fillers = ("嗯", "呃", "那个", "然后", "就是")
        counts = {item: answer.count(item) for item in fillers if item in answer}
        speed = (
            round(len(answer) * 60 / elapsed_seconds)
            if elapsed_seconds and elapsed_seconds > 0
            else None
        )
        return CoachingDeliveryMetrics(
            source="voice_transcript" if answer_mode == "voice" else "text",
            character_count=len(answer),
            characters_per_minute=speed,
            filler_counts=counts,
            filler_total=sum(counts.values()),
        )

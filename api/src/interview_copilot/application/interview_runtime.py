from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from interview_copilot.application.interview_planning import interview_runtime_data
from interview_copilot.domain.interviews import (
    InterviewInterruptionDecision,
    InterviewPlan,
    InterviewQuestionPlan,
    InterviewRuntimeData,
    InterviewTurnDecision,
)
from interview_copilot.infrastructure.interviews import (
    InterviewSessionRecord,
    InterviewTurnRecord,
)


class InterviewTurnError(RuntimeError):
    pass


class InterviewTurnDecider(Protocol):
    model_name: str
    prompt_version: str

    async def decide(
        self,
        *,
        question: str,
        answer: str,
        intent: str,
        skills: list[str],
        follow_up_directions: list[str],
        phase_kind: str,
        pressure_level: int,
        depth_level: int,
        guidance_level: int,
    ) -> InterviewTurnDecision: ...

    async def assess_interruption(
        self,
        *,
        question: str,
        partial_answer: str,
        elapsed_seconds: int,
        pressure_level: int,
        depth_level: int,
        guidance_level: int,
    ) -> InterviewInterruptionDecision: ...


class InterviewRuntimeService:
    def __init__(self, session: Session, decider: InterviewTurnDecider) -> None:
        self._session = session
        self._decider = decider

    def interruption_scope(self, *, user_id: UUID, session_id: UUID) -> str:
        record = self._owned_record(user_id=user_id, session_id=session_id)
        return (
            f"{record.current_phase_index}:{record.current_question_index}:"
            f"{record.follow_up_count}"
        )

    async def answer(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        client_message_id: UUID,
        answer: str,
        answer_mode: str,
    ) -> InterviewRuntimeData:
        existing = self._session.scalar(
            select(InterviewTurnRecord).where(
                InterviewTurnRecord.session_id == session_id,
                InterviewTurnRecord.client_message_id == client_message_id,
            )
        )
        record = self._owned_record(user_id=user_id, session_id=session_id)
        if existing:
            return interview_runtime_data(record)
        if record.status != "started":
            raise ValueError("这场面试当前不能提交回答")

        plan = InterviewPlan.model_validate(record.plan)
        try:
            planned_question = plan.phases[record.current_phase_index].questions[
                record.current_question_index
            ]
        except IndexError as exc:
            raise InterviewTurnError("面试会话进度数据无效") from exc
        active_question = record.active_question or planned_question.prompt
        snapshot = (
            record.current_phase_index,
            record.current_question_index,
            record.follow_up_count,
            active_question,
        )
        decision = await self._decider.decide(
            question=active_question,
            answer=answer,
            intent=planned_question.intent,
            skills=planned_question.skills,
            follow_up_directions=planned_question.follow_up_directions,
            phase_kind=plan.phases[record.current_phase_index].kind,
            pressure_level=record.pressure_level,
            depth_level=record.depth_level,
            guidance_level=record.guidance_level,
        )

        return self._persist_decision(
            user_id=user_id,
            session_id=session_id,
            client_message_id=client_message_id,
            answer=answer,
            answer_mode=answer_mode,
            planned_question=planned_question,
            active_question=active_question,
            snapshot=snapshot,
            decision=decision,
        )

    async def interrupt(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        client_message_id: UUID,
        partial_answer: str,
        elapsed_seconds: int,
    ) -> tuple[bool, InterviewRuntimeData]:
        record = self._owned_record(user_id=user_id, session_id=session_id)
        if record.status != "started":
            raise ValueError("这场面试当前不能判断实时打断")
        if record.pressure_level < 4:
            return False, interview_runtime_data(record)
        plan = InterviewPlan.model_validate(record.plan)
        try:
            planned_question = plan.phases[record.current_phase_index].questions[
                record.current_question_index
            ]
        except IndexError as exc:
            raise InterviewTurnError("面试会话进度数据无效") from exc
        if plan.phases[record.current_phase_index].kind == "candidate_qa":
            return False, interview_runtime_data(record)
        active_question = record.active_question or planned_question.prompt
        snapshot = (
            record.current_phase_index,
            record.current_question_index,
            record.follow_up_count,
            active_question,
        )
        interruption = await self._decider.assess_interruption(
            question=active_question,
            partial_answer=partial_answer,
            elapsed_seconds=elapsed_seconds,
            pressure_level=record.pressure_level,
            depth_level=record.depth_level,
            guidance_level=record.guidance_level,
        )
        if not interruption.should_interrupt:
            return False, interview_runtime_data(record)
        runtime = self._persist_decision(
            user_id=user_id,
            session_id=session_id,
            client_message_id=client_message_id,
            answer=partial_answer,
            answer_mode="voice",
            planned_question=planned_question,
            active_question=active_question,
            snapshot=snapshot,
            decision=InterviewTurnDecision(
                action="follow_up",
                follow_up_question=interruption.follow_up_question,
                rationale=interruption.rationale,
                transition=interruption.transition,
                interviewer_reply=None,
            ),
        )
        return True, runtime

    def _persist_decision(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        client_message_id: UUID,
        answer: str,
        answer_mode: str,
        planned_question: InterviewQuestionPlan,
        active_question: str,
        snapshot: tuple[int, int, int, str],
        decision: InterviewTurnDecision,
    ) -> InterviewRuntimeData:
        locked = self._session.scalar(
            select(InterviewSessionRecord)
            .where(
                InterviewSessionRecord.id == session_id,
                InterviewSessionRecord.user_id == user_id,
            )
            .with_for_update()
        )
        if not locked:
            raise LookupError("找不到这场面试会话")
        duplicate = self._session.scalar(
            select(InterviewTurnRecord).where(
                InterviewTurnRecord.session_id == session_id,
                InterviewTurnRecord.client_message_id == client_message_id,
            )
        )
        if duplicate:
            return interview_runtime_data(locked)
        current = (
            locked.current_phase_index,
            locked.current_question_index,
            locked.follow_up_count,
            locked.active_question or planned_question.prompt,
        )
        if current != snapshot or locked.status != "started":
            raise InterviewTurnError("面试进度已变化，请刷新后重新回答")

        if locked.follow_up_count >= 2 and decision.action == "follow_up":
            decision = InterviewTurnDecision(
                action="next",
                rationale="已达到当前主问题的连续追问上限",
                transition="好的，这部分我了解了。我们继续看下一个问题。",
                interviewer_reply=decision.interviewer_reply,
            )
        sequence = self._session.scalar(
            select(func.coalesce(func.max(InterviewTurnRecord.sequence), 0)).where(
                InterviewTurnRecord.session_id == session_id
            )
        )
        self._session.add(
            InterviewTurnRecord(
                session_id=session_id,
                client_message_id=client_message_id,
                sequence=int(sequence or 0) + 1,
                phase_index=locked.current_phase_index,
                question_index=locked.current_question_index,
                question=active_question,
                answer=answer,
                answer_mode=answer_mode,
                decision=decision.action,
                rationale=decision.rationale,
                transition=decision.transition,
                interviewer_reply=decision.interviewer_reply,
                follow_up_question=decision.follow_up_question,
                model=self._decider.model_name,
                prompt_version=self._decider.prompt_version,
                created_at=datetime.now(UTC),
            )
        )
        if decision.action == "follow_up":
            locked.follow_up_count += 1
            locked.active_question = decision.follow_up_question
        else:
            self._advance(locked, InterviewPlan.model_validate(locked.plan))
        self._session.commit()
        self._session.refresh(locked)
        return interview_runtime_data(locked)

    def _owned_record(self, *, user_id: UUID, session_id: UUID) -> InterviewSessionRecord:
        record = self._session.scalar(
            select(InterviewSessionRecord).where(
                InterviewSessionRecord.id == session_id,
                InterviewSessionRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到这场面试会话")
        return record

    @staticmethod
    def _advance(record: InterviewSessionRecord, plan: InterviewPlan) -> None:
        record.follow_up_count = 0
        phase = plan.phases[record.current_phase_index]
        if record.current_question_index + 1 < len(phase.questions):
            record.current_question_index += 1
        elif record.current_phase_index + 1 < len(plan.phases):
            record.current_phase_index += 1
            record.current_question_index = 0
        else:
            record.status = "completed"
            record.completed_at = datetime.now(UTC)
            record.active_question = None
            return
        record.active_question = (
            plan.phases[record.current_phase_index].questions[record.current_question_index].prompt
        )

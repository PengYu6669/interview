from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session

from interview_copilot.application.claim_verification import ClaimVerificationError
from interview_copilot.domain.interviews import (
    InterviewHistoryItem,
    InterviewPlan,
    InterviewReportBoardSnapshot,
    InterviewReportContent,
    InterviewReportData,
    InterviewReportGenerationData,
    InterviewReportReviewData,
    InterviewReportReviewOutcome,
    InterviewReportReviewRequest,
    InterviewReportTurn,
    ReportGenerationStatus,
    ReportVerificationStatus,
    VerifiedClaim,
)
from interview_copilot.domain.training import TrainingContext
from interview_copilot.infrastructure.boards import InterviewBoardSnapshotRecord
from interview_copilot.infrastructure.interviews import (
    InterviewReportRecord,
    InterviewReportReviewRecord,
    InterviewSessionRecord,
    InterviewTurnRecord,
)


class InterviewReportError(RuntimeError):
    pass


class InterviewReportInProgressError(InterviewReportError):
    pass


class InterviewReportReviewError(InterviewReportError):
    pass


REPORT_GENERATION_TIMEOUT = timedelta(minutes=3)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class InterviewReportGenerator(Protocol):
    model_name: str
    prompt_version: str
    rubric_version: str

    async def generate(
        self,
        *,
        target_role: str,
        session_status: str,
        plan: InterviewPlan,
        turns: list[dict[str, object]],
        verification_status: str,
        verified_claims: list[VerifiedClaim],
        board_snapshot: dict[str, object] | None,
    ) -> InterviewReportContent: ...


class InterviewReportReviewer(Protocol):
    model_name: str
    prompt_version: str

    async def review(
        self,
        *,
        target_role: str,
        skill: str,
        original_score: int,
        evidence: list[dict[str, object]],
        user_reason: str,
    ) -> InterviewReportReviewOutcome: ...


class InterviewReportVerifier(Protocol):
    async def verify(
        self,
        *,
        user_id: UUID,
        turns: list[dict[str, object]],
    ) -> list[VerifiedClaim]: ...


class InterviewReportService:
    def __init__(
        self,
        session: Session,
        generator: InterviewReportGenerator | None = None,
        verifier: InterviewReportVerifier | None = None,
    ) -> None:
        self._session = session
        self._generator = generator
        self._verifier = verifier

    def history(self, *, user_id: UUID) -> list[InterviewHistoryItem]:
        records = self._session.scalars(
            select(InterviewSessionRecord)
            .where(InterviewSessionRecord.user_id == user_id)
            .order_by(InterviewSessionRecord.created_at.desc())
        ).all()
        if not records:
            return []
        session_ids = [record.id for record in records]
        turn_counts: dict[UUID, int] = {
            session_id: int(count)
            for session_id, count in self._session.execute(
                select(InterviewTurnRecord.session_id, func.count(InterviewTurnRecord.id))
                .where(InterviewTurnRecord.session_id.in_(session_ids))
                .group_by(InterviewTurnRecord.session_id)
            ).all()
        }
        report_ids = set(
            self._session.scalars(
                select(InterviewReportRecord.session_id).where(
                    InterviewReportRecord.session_id.in_(session_ids)
                )
            ).all()
        )
        result = []
        for record in records:
            report_status: ReportGenerationStatus = (
                "ready" if record.id in report_ids else self._effective_report_status(record)
            )
            context = TrainingContext.model_validate(
                {
                    "target_company": record.target_company,
                    "target_level": record.target_level,
                    "interview_round": record.interview_round,
                    "interview_type": record.interview_type,
                }
            )
            plan = InterviewPlan.model_validate(record.plan)
            total_questions = sum(len(phase.questions) for phase in plan.phases)
            answered_questions = (
                sum(len(phase.questions) for phase in plan.phases[: record.current_phase_index])
                + record.current_question_index
            )
            if record.status == "completed":
                answered_questions = total_questions
            result.append(
                InterviewHistoryItem(
                    id=record.id,
                    status=record.status,
                    target_role=record.target_role,
                    target_company=context.target_company,
                    target_level=context.target_level,
                    interview_round=context.interview_round,
                    interview_type=context.interview_type,
                    mode=record.mode,
                    duration_minutes=record.duration_minutes,
                    pressure_level=record.pressure_level,
                    depth_level=record.depth_level,
                    guidance_level=record.guidance_level,
                    answered_questions=answered_questions,
                    total_questions=total_questions,
                    turn_count=int(turn_counts.get(record.id, 0)),
                    started_at=record.started_at,
                    completed_at=record.completed_at,
                    report_available=record.id in report_ids,
                    report_status=report_status,
                )
            )
        return result

    def generation_status(
        self, *, user_id: UUID, session_id: UUID
    ) -> InterviewReportGenerationData:
        session = self._owned_session(user_id=user_id, session_id=session_id)
        report_exists = self._session.scalar(
            select(InterviewReportRecord.id).where(
                InterviewReportRecord.session_id == session_id,
                InterviewReportRecord.user_id == user_id,
            )
        )
        status: ReportGenerationStatus = (
            "ready" if report_exists else self._effective_report_status(session)
        )
        messages = {
            "not_started": "报告尚未生成",
            "generating": "正在核对回答证据并生成复盘报告",
            "ready": "复盘报告已生成并保存",
            "failed": session.report_error or "上次生成未完成，可以重新尝试",
        }
        return InterviewReportGenerationData(
            session_id=session.id,
            status=status,
            message=messages[status],
            started_at=session.report_generation_started_at,
            finished_at=session.report_generation_finished_at,
        )

    def get(self, *, user_id: UUID, session_id: UUID) -> InterviewReportData:
        record = self._session.scalar(
            select(InterviewReportRecord).where(
                InterviewReportRecord.session_id == session_id,
                InterviewReportRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("这场面试还没有生成报告")
        session = self._owned_session(user_id=user_id, session_id=session_id)
        return self._to_domain(record, session)

    async def review(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request: InterviewReportReviewRequest,
        reviewer: InterviewReportReviewer | None,
    ) -> InterviewReportReviewData:
        existing = self._session.scalar(
            select(InterviewReportReviewRecord).where(
                InterviewReportReviewRecord.user_id == user_id,
                InterviewReportReviewRecord.client_request_id == request.client_request_id,
            )
        )
        if existing:
            if existing.session_id != session_id:
                raise ValueError("该请求标识已用于其他面试报告")
            return self._to_review_domain(existing)

        report = self._session.scalar(
            select(InterviewReportRecord).where(
                InterviewReportRecord.session_id == session_id,
                InterviewReportRecord.user_id == user_id,
            )
        )
        if not report:
            raise LookupError("这场面试还没有可复核的报告")
        session = self._owned_session(user_id=user_id, session_id=session_id)
        content = InterviewReportContent.model_validate(report.content)
        if request.skill_index >= len(content.skill_scores):
            raise ValueError("要复核的能力评分不存在")
        score = content.skill_scores[request.skill_index]
        now = datetime.now(UTC)
        record = InterviewReportReviewRecord(
            report_id=report.id,
            session_id=session_id,
            user_id=user_id,
            client_request_id=request.client_request_id,
            skill_index=request.skill_index,
            skill=score.skill,
            original_score=score.score,
            action=request.action,
            reason=request.reason.strip(),
            status="resolved" if request.action == "exclude" else "pending",
            decision="excluded" if request.action == "exclude" else None,
            rationale=(
                "已按你的选择从能力画像聚合中排除；原报告和回答证据仍保留。"
                if request.action == "exclude"
                else None
            ),
            revised_score=None,
            confidence=1.0 if request.action == "exclude" else None,
            model=None,
            prompt_version=None,
            created_at=now,
            resolved_at=now if request.action == "exclude" else None,
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            concurrent = self._session.scalar(
                select(InterviewReportReviewRecord).where(
                    InterviewReportReviewRecord.user_id == user_id,
                    InterviewReportReviewRecord.client_request_id == request.client_request_id,
                )
            )
            if concurrent:
                return self._to_review_domain(concurrent)
            raise
        self._session.refresh(record)
        if request.action == "exclude":
            return self._to_review_domain(record)
        if not reviewer:
            self._mark_review_failed(record, "报告复核服务尚未配置")
            raise InterviewReportReviewError("报告复核服务尚未配置")

        turns = self._session.scalars(
            select(InterviewTurnRecord)
            .where(
                InterviewTurnRecord.session_id == session_id,
                InterviewTurnRecord.sequence.in_(score.evidence_turns),
            )
            .order_by(InterviewTurnRecord.sequence)
        ).all()
        evidence = [
            {
                "sequence": turn.sequence,
                "question": turn.question,
                "answer": turn.answer,
            }
            for turn in turns
        ]
        try:
            outcome = await reviewer.review(
                target_role=session.target_role,
                skill=score.skill,
                original_score=score.score,
                evidence=evidence,
                user_reason=request.reason.strip(),
            )
        except InterviewReportReviewError as exc:
            self._mark_review_failed(record, str(exc))
            raise
        record.status = "resolved"
        record.decision = outcome.decision
        record.rationale = outcome.rationale
        record.revised_score = outcome.revised_score
        record.confidence = outcome.confidence
        record.model = reviewer.model_name
        record.prompt_version = reviewer.prompt_version
        record.resolved_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(record)
        return self._to_review_domain(record)

    async def generate(self, *, user_id: UUID, session_id: UUID) -> InterviewReportData:
        session = self._owned_session(user_id=user_id, session_id=session_id)
        existing = self._session.scalar(
            select(InterviewReportRecord).where(
                InterviewReportRecord.session_id == session_id,
                InterviewReportRecord.user_id == user_id,
            )
        )
        if existing:
            return self._to_domain(existing, session)
        if session.status not in {"completed", "ended"}:
            raise ValueError("只有已完成或已结束的面试可以生成报告")
        turns = self._session.scalars(
            select(InterviewTurnRecord)
            .where(InterviewTurnRecord.session_id == session_id)
            .order_by(InterviewTurnRecord.sequence)
        ).all()
        if not turns:
            raise ValueError("这场面试没有可用于生成报告的回答证据")
        if not self._generator:
            raise InterviewReportError("面试报告生成器尚未配置")
        attempt_id = self._claim_generation(user_id=user_id, session_id=session_id)
        turn_data: list[dict[str, object]] = [
            {
                "sequence": turn.sequence,
                "phase_index": turn.phase_index,
                "question_index": turn.question_index,
                "question": turn.question,
                "answer": turn.answer,
                "answer_mode": turn.answer_mode,
                "decision": turn.decision,
                "interviewer_reply": turn.interviewer_reply,
                "follow_up_question": turn.follow_up_question,
            }
            for turn in turns
        ]
        board_record = self._session.scalar(
            select(InterviewBoardSnapshotRecord)
            .where(
                InterviewBoardSnapshotRecord.session_id == session_id,
                InterviewBoardSnapshotRecord.user_id == user_id,
            )
            .order_by(InterviewBoardSnapshotRecord.revision.desc())
        )
        board_snapshot: dict[str, object] | None = (
            {
                "revision": board_record.revision,
                "state": board_record.state,
                "created_at": board_record.created_at.isoformat(),
            }
            if board_record
            else None
        )
        verification_status = "not_run"
        verification_error: str | None = None
        verified_claims: list[VerifiedClaim] = []
        if self._verifier:
            try:
                verified_claims = await self._verifier.verify(
                    user_id=user_id,
                    turns=turn_data,
                )
                verification_status = "completed"
            except ClaimVerificationError as exc:
                verification_status = "degraded"
                verification_error = str(exc)[:500]
        try:
            content = await self._generator.generate(
                target_role=session.target_role,
                session_status=session.status,
                plan=InterviewPlan.model_validate(session.plan),
                turns=turn_data,
                verification_status=verification_status,
                verified_claims=verified_claims,
                board_snapshot=board_snapshot,
            )
            self._validate_evidence(content, turns)
        except InterviewReportError as exc:
            self._mark_generation_failed(
                user_id=user_id,
                session_id=session_id,
                attempt_id=attempt_id,
                message=str(exc),
            )
            raise
        locked_session = self._session.scalar(
            select(InterviewSessionRecord)
            .where(
                InterviewSessionRecord.id == session_id,
                InterviewSessionRecord.user_id == user_id,
            )
            .with_for_update()
        )
        if not locked_session:
            raise LookupError("找不到这场面试会话")
        if locked_session.report_generation_id != attempt_id:
            raise InterviewReportInProgressError("报告生成任务已更新，请等待当前任务完成")
        record = InterviewReportRecord(
            session_id=session_id,
            user_id=user_id,
            content=content.model_dump(mode="json"),
            verification_status=verification_status,
            verification_error=verification_error,
            verified_claims=[item.model_dump(mode="json") for item in verified_claims],
            board_snapshot=(
                {
                    "revision": board_record.revision,
                    "state": board_record.state,
                    "created_at": board_record.created_at.isoformat(),
                }
                if board_record
                else None
            ),
            model=self._generator.model_name,
            prompt_version=self._generator.prompt_version,
            rubric_version=self._generator.rubric_version,
            created_at=datetime.now(UTC),
        )
        self._session.add(record)
        locked_session.report_status = "ready"
        locked_session.report_error = None
        locked_session.report_generation_finished_at = datetime.now(UTC)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            existing = self._session.scalar(
                select(InterviewReportRecord).where(
                    InterviewReportRecord.session_id == session_id,
                    InterviewReportRecord.user_id == user_id,
                )
            )
            if existing:
                completed_session = self._owned_session(user_id=user_id, session_id=session_id)
                completed_session.report_status = "ready"
                completed_session.report_error = None
                completed_session.report_generation_finished_at = datetime.now(UTC)
                self._session.commit()
                return self._to_domain(existing, completed_session)
            self._mark_generation_failed(
                user_id=user_id,
                session_id=session_id,
                attempt_id=attempt_id,
                message="面试报告保存失败",
            )
            raise InterviewReportError("面试报告保存失败") from exc
        self._session.refresh(record)
        return self._to_domain(record, locked_session)

    def _claim_generation(self, *, user_id: UUID, session_id: UUID) -> UUID:
        session = self._session.scalar(
            select(InterviewSessionRecord)
            .where(
                InterviewSessionRecord.id == session_id,
                InterviewSessionRecord.user_id == user_id,
            )
            .with_for_update()
        )
        if not session:
            raise LookupError("找不到这场面试会话")
        if self._effective_report_status(session) == "generating":
            raise InterviewReportInProgressError("复盘报告正在生成，请稍后查看")
        attempt_id = uuid4()
        session.report_status = "generating"
        session.report_error = None
        session.report_generation_id = attempt_id
        session.report_generation_started_at = datetime.now(UTC)
        session.report_generation_finished_at = None
        self._session.commit()
        return attempt_id

    def _mark_generation_failed(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        attempt_id: UUID,
        message: str,
    ) -> None:
        session = self._session.scalar(
            select(InterviewSessionRecord)
            .where(
                InterviewSessionRecord.id == session_id,
                InterviewSessionRecord.user_id == user_id,
            )
            .with_for_update()
        )
        if not session or session.report_generation_id != attempt_id:
            return
        session.report_status = "failed"
        session.report_error = message[:500]
        session.report_generation_finished_at = datetime.now(UTC)
        self._session.commit()

    def _mark_review_failed(
        self,
        record: InterviewReportReviewRecord,
        message: str,
    ) -> None:
        record.status = "failed"
        record.rationale = message[:1_000]
        record.resolved_at = datetime.now(UTC)
        self._session.commit()

    @staticmethod
    def _effective_report_status(
        session: InterviewSessionRecord,
    ) -> ReportGenerationStatus:
        if (
            session.report_status == "generating"
            and session.report_generation_started_at
            and datetime.now(UTC) - _utc(session.report_generation_started_at)
            > REPORT_GENERATION_TIMEOUT
        ):
            return "failed"
        if session.report_status in {"not_started", "generating", "ready", "failed"}:
            return cast(ReportGenerationStatus, session.report_status)
        return "not_started"

    def _owned_session(self, *, user_id: UUID, session_id: UUID) -> InterviewSessionRecord:
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
    def _validate_evidence(
        content: InterviewReportContent,
        turns: Sequence[InterviewTurnRecord],
    ) -> None:
        answers = {turn.sequence: turn.answer for turn in turns}
        for score in content.skill_scores:
            if any(sequence not in answers for sequence in score.evidence_turns):
                raise InterviewReportError("面试报告引用了不存在的回答轮次")
        for finding in [*content.strengths, *content.improvements]:
            if any(sequence not in answers for sequence in finding.evidence_turns):
                raise InterviewReportError("面试报告引用了不存在的回答轮次")
            source = "\n".join(answers[sequence] for sequence in finding.evidence_turns)
            if finding.evidence_quote not in source:
                raise InterviewReportError("面试报告引用的原话不属于对应回答")

    def _to_domain(
        self,
        record: InterviewReportRecord,
        session: InterviewSessionRecord,
    ) -> InterviewReportData:
        plan = InterviewPlan.model_validate(session.plan)
        context = TrainingContext.model_validate(
            {
                "target_company": session.target_company,
                "target_level": session.target_level,
                "interview_round": session.interview_round,
                "interview_type": session.interview_type,
            }
        )
        turns: list[InterviewTurnRecord] = []
        db_session = object_session(record)
        if db_session is not None:
            turns = list(
                db_session.scalars(
                    select(InterviewTurnRecord)
                    .where(InterviewTurnRecord.session_id == session.id)
                    .order_by(InterviewTurnRecord.sequence)
                ).all()
            )
        review_records: list[InterviewReportReviewRecord] = []
        if db_session is not None:
            review_records = list(
                db_session.scalars(
                    select(InterviewReportReviewRecord)
                    .where(InterviewReportReviewRecord.report_id == record.id)
                    .order_by(InterviewReportReviewRecord.created_at)
                ).all()
            )
        return InterviewReportData(
            session_id=session.id,
            target_role=session.target_role,
            target_company=context.target_company,
            target_level=context.target_level,
            interview_round=context.interview_round,
            interview_type=context.interview_type,
            mode=session.mode,
            pressure_level=session.pressure_level,
            depth_level=session.depth_level,
            guidance_level=session.guidance_level,
            session_status=session.status,
            duration_minutes=session.duration_minutes,
            turn_count=len(turns),
            turns=[
                InterviewReportTurn(
                    sequence=turn.sequence,
                    phase_index=turn.phase_index,
                    phase_name=plan.phases[turn.phase_index].name,
                    question_index=turn.question_index,
                    question_number=(
                        sum(len(phase.questions) for phase in plan.phases[: turn.phase_index])
                        + turn.question_index
                        + 1
                    ),
                    question=turn.question,
                    answer=turn.answer,
                    answer_mode=turn.answer_mode,
                    decision=turn.decision,
                    transition=turn.transition,
                    interviewer_reply=turn.interviewer_reply,
                    follow_up_question=turn.follow_up_question,
                    created_at=turn.created_at,
                )
                for turn in turns
            ],
            board_snapshot=(
                InterviewReportBoardSnapshot.model_validate(record.board_snapshot)
                if record.board_snapshot
                else None
            ),
            content=InterviewReportContent.model_validate(record.content),
            reviews=[self._to_review_domain(item) for item in review_records],
            verification_status=cast(ReportVerificationStatus, record.verification_status),
            verification_error=record.verification_error,
            verified_claims=[VerifiedClaim.model_validate(item) for item in record.verified_claims],
            model=record.model,
            prompt_version=record.prompt_version,
            rubric_version=record.rubric_version,
            created_at=record.created_at,
        )

    @staticmethod
    def _to_review_domain(record: InterviewReportReviewRecord) -> InterviewReportReviewData:
        return InterviewReportReviewData.model_validate(
            {
                "id": record.id,
                "session_id": record.session_id,
                "skill_index": record.skill_index,
                "skill": record.skill,
                "original_score": record.original_score,
                "action": record.action,
                "reason": record.reason,
                "status": record.status,
                "decision": record.decision,
                "rationale": record.rationale,
                "revised_score": record.revised_score,
                "confidence": record.confidence,
                "model": record.model,
                "prompt_version": record.prompt_version,
                "created_at": record.created_at,
                "resolved_at": record.resolved_at,
            }
        )

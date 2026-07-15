from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from interview_copilot.domain.account import (
    AccountDataExport,
    AccountDataSummary,
    ExportDraft,
    ExportInterviewReport,
    ExportInterviewReportReview,
    ExportInterviewSession,
    ExportInterviewTurn,
    ExportLearningState,
    ExportPrivateQuestion,
    ExportQuestionConversation,
    ExportQuestionMessage,
)
from interview_copilot.domain.auth import UserProfile
from interview_copilot.infrastructure.coding import (
    InterviewCodingRunRecord,
    InterviewCodingSnapshotRecord,
)
from interview_copilot.infrastructure.database import UserRecord
from interview_copilot.infrastructure.drafts import (
    TrainingDraftQuestionRecord,
    TrainingDraftRecord,
)
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

OwnerId = TypeVar("OwnerId", UUID, UUID | None)


class AccountNotFoundError(LookupError):
    pass


class CurrentPasswordError(ValueError):
    pass


class AccountDataService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._passwords = PasswordHasher()

    def summary(self, *, user_id: UUID) -> AccountDataSummary:
        user = self._user(user_id)
        return AccountDataSummary(
            account=UserProfile.model_validate(user),
            draft_count=self._count(TrainingDraftRecord, TrainingDraftRecord.user_id, user_id),
            interview_count=self._count(
                InterviewSessionRecord, InterviewSessionRecord.user_id, user_id
            ),
            report_count=self._count(InterviewReportRecord, InterviewReportRecord.user_id, user_id),
            private_question_count=self._count(
                QuestionRecord, QuestionRecord.owner_user_id, user_id
            ),
            note_count=self._count(UserQuestionNoteRecord, UserQuestionNoteRecord.user_id, user_id),
        )

    def export(self, *, user_id: UUID) -> AccountDataExport:
        user = self._user(user_id)
        drafts = self._session.scalars(
            select(TrainingDraftRecord)
            .where(TrainingDraftRecord.user_id == user_id)
            .order_by(TrainingDraftRecord.created_at)
        ).all()
        draft_questions = self._draft_question_map([draft.id for draft in drafts])
        interviews = self._session.scalars(
            select(InterviewSessionRecord)
            .where(InterviewSessionRecord.user_id == user_id)
            .order_by(InterviewSessionRecord.created_at)
        ).all()
        interview_exports = [self._export_interview(record) for record in interviews]
        private_questions = self._session.scalars(
            select(QuestionRecord)
            .where(QuestionRecord.owner_user_id == user_id)
            .order_by(QuestionRecord.created_at)
        ).all()
        learning_states = self._learning_states(user_id)
        conversations = self._question_conversations(user_id)
        return AccountDataExport(
            exported_at=datetime.now(UTC),
            account=UserProfile.model_validate(user),
            training_drafts=[
                ExportDraft(
                    id=draft.id,
                    resume_filename=draft.resume_filename,
                    resume_text=draft.resume_text,
                    jd=draft.jd,
                    target_role=draft.target_role,
                    target_company=draft.target_company,
                    target_level=draft.target_level,
                    interview_round=draft.interview_round,
                    interview_type=draft.interview_type,
                    mode=draft.mode,
                    duration_minutes=draft.duration_minutes,
                    pressure_level=draft.pressure_level,
                    depth_level=draft.depth_level,
                    guidance_level=draft.guidance_level,
                    training_focus=draft.training_focus,
                    extraction=draft.extraction,
                    question_ids=draft_questions.get(draft.id, []),
                    created_at=draft.created_at,
                    updated_at=draft.updated_at,
                    expires_at=draft.expires_at,
                )
                for draft in drafts
            ],
            interview_sessions=interview_exports,
            private_questions=[
                ExportPrivateQuestion(
                    id=question.id,
                    slug=question.slug,
                    title=question.title,
                    prompt=question.prompt,
                    difficulty=question.difficulty,
                    question_type=question.question_type,
                    intent=question.intent,
                    answer_outline=question.answer_outline,
                    common_mistakes=question.common_mistakes,
                    content_markdown=question.content_markdown,
                    source_document_name=question.source_document_name,
                    created_at=question.created_at,
                )
                for question in private_questions
            ],
            learning_states=learning_states,
            question_conversations=conversations,
        )

    def delete_account(self, *, user_id: UUID, current_password: str) -> None:
        user = self._session.scalar(
            select(UserRecord).where(UserRecord.id == user_id).with_for_update()
        )
        if not user:
            raise AccountNotFoundError("账号不存在")
        try:
            verified = bool(self._passwords.verify(user.password_hash, current_password))
        except (VerifyMismatchError, InvalidHashError):
            verified = False
        if not verified:
            raise CurrentPasswordError("当前密码不正确")

        draft_ids = select(TrainingDraftRecord.id).where(TrainingDraftRecord.user_id == user_id)
        private_question_ids = select(QuestionRecord.id).where(
            QuestionRecord.owner_user_id == user_id
        )
        self._session.execute(
            delete(InterviewSessionRecord).where(InterviewSessionRecord.user_id == user_id)
        )
        self._session.execute(
            delete(TrainingDraftQuestionRecord).where(
                TrainingDraftQuestionRecord.draft_id.in_(draft_ids)
            )
        )
        self._session.execute(
            delete(TrainingDraftQuestionRecord).where(
                TrainingDraftQuestionRecord.question_id.in_(private_question_ids)
            )
        )
        self._session.execute(
            delete(TrainingDraftRecord).where(TrainingDraftRecord.user_id == user_id)
        )
        self._session.execute(delete(QuestionRecord).where(QuestionRecord.owner_user_id == user_id))
        self._session.delete(user)
        self._session.commit()

    def _user(self, user_id: UUID) -> UserRecord:
        user = self._session.get(UserRecord, user_id)
        if not user:
            raise AccountNotFoundError("账号不存在")
        return user

    def _count(
        self,
        model: type,
        owner_column: InstrumentedAttribute[OwnerId],
        user_id: UUID,
    ) -> int:
        statement = select(func.count()).select_from(model).where(owner_column == user_id)
        return int(self._session.scalar(statement) or 0)

    def _draft_question_map(self, draft_ids: list[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {draft_id: [] for draft_id in draft_ids}
        if not draft_ids:
            return result
        rows = self._session.execute(
            select(
                TrainingDraftQuestionRecord.draft_id,
                TrainingDraftQuestionRecord.question_id,
            ).where(TrainingDraftQuestionRecord.draft_id.in_(draft_ids))
        ).all()
        for draft_id, question_id in rows:
            result[draft_id].append(question_id)
        return result

    def _export_interview(self, record: InterviewSessionRecord) -> ExportInterviewSession:
        turns = self._session.scalars(
            select(InterviewTurnRecord)
            .where(InterviewTurnRecord.session_id == record.id)
            .order_by(InterviewTurnRecord.sequence)
        ).all()
        report = self._session.scalar(
            select(InterviewReportRecord).where(InterviewReportRecord.session_id == record.id)
        )
        reviews = (
            self._session.scalars(
                select(InterviewReportReviewRecord)
                .where(InterviewReportReviewRecord.report_id == report.id)
                .order_by(InterviewReportReviewRecord.created_at)
            ).all()
            if report
            else []
        )
        coding_snapshots = self._session.scalars(
            select(InterviewCodingSnapshotRecord)
            .where(InterviewCodingSnapshotRecord.session_id == record.id)
            .order_by(
                InterviewCodingSnapshotRecord.phase_index,
                InterviewCodingSnapshotRecord.question_index,
                InterviewCodingSnapshotRecord.revision,
            )
        ).all()
        coding_runs = self._session.scalars(
            select(InterviewCodingRunRecord)
            .where(InterviewCodingRunRecord.session_id == record.id)
            .order_by(InterviewCodingRunRecord.created_at)
        ).all()
        return ExportInterviewSession(
            id=record.id,
            draft_id=record.draft_id,
            status=record.status,
            target_role=record.target_role,
            target_company=record.target_company,
            target_level=record.target_level,
            interview_round=record.interview_round,
            interview_type=record.interview_type,
            mode=record.mode,
            duration_minutes=record.duration_minutes,
            pressure_level=record.pressure_level,
            depth_level=record.depth_level,
            guidance_level=record.guidance_level,
            training_focus=record.training_focus,
            summary=record.summary,
            plan=record.plan,
            model=record.model,
            prompt_version=record.prompt_version,
            created_at=record.created_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            turns=[
                ExportInterviewTurn(
                    sequence=turn.sequence,
                    phase_index=turn.phase_index,
                    question_index=turn.question_index,
                    question=turn.question,
                    answer=turn.answer,
                    answer_mode=turn.answer_mode,
                    decision=turn.decision,
                    rationale=turn.rationale,
                    transition=turn.transition,
                    interviewer_reply=turn.interviewer_reply,
                    follow_up_question=turn.follow_up_question,
                    model=turn.model,
                    prompt_version=turn.prompt_version,
                    created_at=turn.created_at,
                )
                for turn in turns
            ],
            coding_snapshots=[
                {
                    "id": item.id,
                    "phase_index": item.phase_index,
                    "question_index": item.question_index,
                    "revision": item.revision,
                    "source": item.source,
                    "complexity_notes": item.complexity_notes,
                    "created_at": item.created_at,
                }
                for item in coding_snapshots
            ],
            coding_runs=[
                {
                    "id": item.id,
                    "snapshot_id": item.snapshot_id,
                    "status": item.status,
                    "tests": item.tests,
                    "duration_ms": item.duration_ms,
                    "error": item.error,
                    "created_at": item.created_at,
                }
                for item in coding_runs
            ],
            report=(
                ExportInterviewReport(
                    content=report.content,
                    verification_status=report.verification_status,
                    verification_error=report.verification_error,
                    verified_claims=report.verified_claims,
                    board_snapshot=report.board_snapshot,
                    coding_evidence=report.coding_evidence,
                    model=report.model,
                    prompt_version=report.prompt_version,
                    rubric_version=report.rubric_version,
                    created_at=report.created_at,
                    reviews=[
                        ExportInterviewReportReview(
                            id=review.id,
                            skill_index=review.skill_index,
                            skill=review.skill,
                            original_score=review.original_score,
                            action=review.action,
                            reason=review.reason,
                            status=review.status,
                            decision=review.decision,
                            rationale=review.rationale,
                            revised_score=review.revised_score,
                            confidence=review.confidence,
                            model=review.model,
                            prompt_version=review.prompt_version,
                            created_at=review.created_at,
                            resolved_at=review.resolved_at,
                        )
                        for review in reviews
                    ],
                )
                if report
                else None
            ),
        )

    def _learning_states(self, user_id: UUID) -> list[ExportLearningState]:
        progress_rows = self._session.scalars(
            select(UserQuestionProgressRecord).where(UserQuestionProgressRecord.user_id == user_id)
        ).all()
        note_rows = self._session.scalars(
            select(UserQuestionNoteRecord).where(UserQuestionNoteRecord.user_id == user_id)
        ).all()
        notes = {row.question_id: row for row in note_rows}
        question_ids = {row.question_id for row in progress_rows} | set(notes)
        progress = {row.question_id: row for row in progress_rows}
        result: list[ExportLearningState] = []
        for question_id in sorted(question_ids, key=str):
            state = progress.get(question_id)
            note = notes.get(question_id)
            updated_candidates = [row.updated_at for row in (state, note) if row]
            result.append(
                ExportLearningState(
                    question_id=question_id,
                    status=state.status if state else "unseen",
                    bookmarked=state.bookmarked if state else False,
                    note=note.content if note else "",
                    updated_at=max(updated_candidates),
                    review_interval_days=state.review_interval_days if state else 0,
                    review_streak=state.review_streak if state else 0,
                    last_reviewed_at=state.last_reviewed_at if state else None,
                    review_due_at=state.review_due_at if state else None,
                )
            )
        return result

    def _question_conversations(self, user_id: UUID) -> list[ExportQuestionConversation]:
        conversations = self._session.scalars(
            select(QuestionConversationRecord)
            .where(QuestionConversationRecord.user_id == user_id)
            .order_by(QuestionConversationRecord.created_at)
        ).all()
        result: list[ExportQuestionConversation] = []
        for conversation in conversations:
            messages = self._session.scalars(
                select(QuestionMessageRecord)
                .where(QuestionMessageRecord.conversation_id == conversation.id)
                .order_by(QuestionMessageRecord.created_at)
            ).all()
            result.append(
                ExportQuestionConversation(
                    id=conversation.id,
                    question_id=conversation.question_id,
                    created_at=conversation.created_at,
                    messages=[
                        ExportQuestionMessage(
                            role=message.role,
                            content=message.content,
                            citations=message.citations,
                            created_at=message.created_at,
                        )
                        for message in messages
                    ],
                )
            )
        return result

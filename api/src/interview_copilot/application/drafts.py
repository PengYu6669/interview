from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from interview_copilot.domain.draft import TrainingDraftData
from interview_copilot.domain.resume import ResumeProfile
from interview_copilot.domain.training import TrainingContext
from interview_copilot.infrastructure.drafts import (
    TrainingDraftQuestionRecord,
    TrainingDraftRecord,
    get_owned_draft,
)
from interview_copilot.infrastructure.interviews import InterviewSessionRecord
from interview_copilot.infrastructure.questions import QuestionRecord


class DraftLockedError(RuntimeError):
    pass


class DraftService:
    def __init__(self, session: Session, *, retention_days: int) -> None:
        self._session = session
        self._retention = timedelta(days=retention_days)

    def create(self, *, user_id: UUID, data: dict) -> TrainingDraftData:
        now = datetime.now(UTC)
        question_ids = self._validated_question_ids(
            user_id=user_id,
            question_ids=data.pop("question_ids", []),
        )
        record = TrainingDraftRecord(
            user_id=user_id,
            **data,
            created_at=now,
            updated_at=now,
            expires_at=now + self._retention,
        )
        self._session.add(record)
        self._session.flush()
        self._session.add_all(
            TrainingDraftQuestionRecord(draft_id=record.id, question_id=question_id)
            for question_id in question_ids
        )
        self._session.commit()
        self._session.refresh(record)
        return self._to_domain(record)

    def get(self, *, user_id: UUID, draft_id: UUID) -> TrainingDraftData:
        record = get_owned_draft(self._session, draft_id, user_id)
        if not record:
            raise LookupError("找不到这份训练草稿")
        return self._to_domain(record)

    def update(self, *, user_id: UUID, draft_id: UUID, data: dict) -> TrainingDraftData:
        record = get_owned_draft(self._session, draft_id, user_id)
        if not record:
            raise LookupError("找不到这份训练草稿")
        question_ids = data.pop("question_ids", None)
        current_question_ids = list(
            self._session.scalars(
                select(TrainingDraftQuestionRecord.question_id).where(
                    TrainingDraftQuestionRecord.draft_id == record.id
                )
            ).all()
        )
        has_changes = any(getattr(record, key) != value for key, value in data.items())
        if question_ids is not None and set(question_ids) != set(current_question_ids):
            has_changes = True
        if has_changes and self._session.scalar(
            select(InterviewSessionRecord.id).where(
                InterviewSessionRecord.draft_id == record.id
            )
        ):
            raise DraftLockedError("这份草稿已生成面试计划，请保存为新的训练版本")
        validated_question_ids = (
            self._validated_question_ids(user_id=user_id, question_ids=question_ids)
            if question_ids is not None
            else None
        )
        for key, value in data.items():
            setattr(record, key, value)
        if validated_question_ids is not None:
            self._session.execute(
                delete(TrainingDraftQuestionRecord).where(
                    TrainingDraftQuestionRecord.draft_id == record.id
                )
            )
            self._session.add_all(
                TrainingDraftQuestionRecord(draft_id=record.id, question_id=question_id)
                for question_id in validated_question_ids
            )
        record.updated_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(record)
        return self._to_domain(record)

    def delete(self, *, user_id: UUID, draft_id: UUID) -> None:
        record = get_owned_draft(self._session, draft_id, user_id)
        if not record:
            raise LookupError("找不到这份训练草稿")
        self._session.delete(record)
        self._session.commit()

    def _to_domain(self, record: TrainingDraftRecord) -> TrainingDraftData:
        extraction = ResumeProfile.model_validate(record.extraction) if record.extraction else None
        context = TrainingContext.model_validate(
            {
                "target_company": record.target_company,
                "target_level": record.target_level,
                "interview_round": record.interview_round,
                "interview_type": record.interview_type,
            }
        )
        return TrainingDraftData(
            id=record.id,
            resume_filename=record.resume_filename,
            resume_text=record.resume_text,
            jd=record.jd,
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
            question_ids=list(
                self._session.scalars(
                    select(TrainingDraftQuestionRecord.question_id).where(
                        TrainingDraftQuestionRecord.draft_id == record.id
                    )
                ).all()
            ),
            training_focus=record.training_focus,
            extraction=extraction,
            created_at=record.created_at,
            updated_at=record.updated_at,
            expires_at=record.expires_at,
        )

    def _validated_question_ids(
        self,
        *,
        user_id: UUID,
        question_ids: list[UUID],
    ) -> list[UUID]:
        unique_ids = list(dict.fromkeys(question_ids))
        if not unique_ids:
            return []
        available_ids = set(
            self._session.scalars(
                select(QuestionRecord.id).where(
                    QuestionRecord.id.in_(unique_ids),
                    or_(
                        QuestionRecord.published.is_(True),
                        QuestionRecord.owner_user_id == user_id,
                    ),
                )
            ).all()
        )
        if available_ids != set(unique_ids):
            raise ValueError("所选题目中包含不存在或无权使用的内容")
        return unique_ids

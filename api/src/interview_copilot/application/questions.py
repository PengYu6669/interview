from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from interview_copilot.domain.questions import (
    QuestionDetail,
    QuestionSummary,
    SourceData,
    TopicData,
    UserQuestionState,
)
from interview_copilot.infrastructure.questions import (
    QuestionRecord,
    TopicRecord,
    UserQuestionNoteRecord,
    UserQuestionProgressRecord,
)


class QuestionBankService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_questions(self, *, topic: str | None, difficulty: str | None) -> list[QuestionSummary]:
        statement = (
            select(QuestionRecord)
            .where(QuestionRecord.published.is_(True))
            .options(selectinload(QuestionRecord.topics))
        )
        if topic:
            statement = statement.where(QuestionRecord.topics.any(TopicRecord.slug == topic))
        if difficulty:
            statement = statement.where(QuestionRecord.difficulty == difficulty)
        records = self._session.scalars(statement.order_by(QuestionRecord.created_at)).all()
        return [self._summary(item) for item in records]

    def list_owned(self, user_id: UUID) -> list[QuestionSummary]:
        records = self._session.scalars(
            select(QuestionRecord)
            .where(QuestionRecord.owner_user_id == user_id)
            .options(selectinload(QuestionRecord.topics))
            .order_by(QuestionRecord.created_at.desc())
        ).all()
        return [self._summary(item) for item in records]

    def list_review_due(self, *, user_id: UUID) -> list[QuestionSummary]:
        now = datetime.now(UTC)
        records = self._session.scalars(
            select(QuestionRecord)
            .join(
                UserQuestionProgressRecord,
                UserQuestionProgressRecord.question_id == QuestionRecord.id,
            )
            .where(
                UserQuestionProgressRecord.user_id == user_id,
                UserQuestionProgressRecord.review_due_at.is_not(None),
                UserQuestionProgressRecord.review_due_at <= now,
                or_(QuestionRecord.published.is_(True), QuestionRecord.owner_user_id == user_id),
            )
            .options(selectinload(QuestionRecord.topics))
            .order_by(UserQuestionProgressRecord.review_due_at, QuestionRecord.created_at)
        ).all()
        return [self._summary(item) for item in records]

    def get_question(self, slug: str, *, user_id: UUID | None = None) -> QuestionDetail:
        record = self._session.scalar(
            select(QuestionRecord)
            .where(QuestionRecord.slug == slug)
            .options(selectinload(QuestionRecord.topics), selectinload(QuestionRecord.sources))
        )
        if not record:
            raise LookupError("找不到这道题目")
        if not record.published and record.owner_user_id != user_id:
            raise LookupError("找不到这道题目")
        return self._detail(
            record,
            editable=record.owner_user_id is not None and record.owner_user_id == user_id,
        )

    def _detail(self, record: QuestionRecord, *, editable: bool) -> QuestionDetail:
        return QuestionDetail(
            **self._summary(record).model_dump(),
            intent=record.intent,
            answer_outline=record.answer_outline,
            common_mistakes=record.common_mistakes,
            sources=[
                SourceData(title=item.title, url=item.url, publisher=item.publisher)
                for item in record.sources
            ],
            content_markdown=record.content_markdown,
            editable=editable,
            source_document_name=record.source_document_name,
        )

    def get_user_state(self, *, user_id: UUID, question_id: UUID) -> UserQuestionState:
        progress = self._session.scalar(
            select(UserQuestionProgressRecord).where(
                UserQuestionProgressRecord.user_id == user_id,
                UserQuestionProgressRecord.question_id == question_id,
            )
        )
        note = self._session.scalar(
            select(UserQuestionNoteRecord).where(
                UserQuestionNoteRecord.user_id == user_id,
                UserQuestionNoteRecord.question_id == question_id,
            )
        )
        return UserQuestionState(
            status=progress.status if progress else "unseen",
            bookmarked=progress.bookmarked if progress else False,
            note=note.content if note else "",
            review_interval_days=progress.review_interval_days if progress else 0,
            review_streak=progress.review_streak if progress else 0,
            last_reviewed_at=progress.last_reviewed_at if progress else None,
            review_due_at=progress.review_due_at if progress else None,
        )

    def update_state(
        self, *, user_id: UUID, question_id: UUID, status: str, bookmarked: bool, note: str
    ) -> UserQuestionState:
        if not self._session.get(QuestionRecord, question_id):
            raise LookupError("找不到这道题目")
        now = datetime.now(UTC)
        progress = self._session.scalar(
            select(UserQuestionProgressRecord).where(
                UserQuestionProgressRecord.user_id == user_id,
                UserQuestionProgressRecord.question_id == question_id,
            )
        )
        if not progress:
            progress = UserQuestionProgressRecord(
                user_id=user_id, question_id=question_id, updated_at=now
            )
            self._session.add(progress)
            progress.review_interval_days = 0
            progress.review_streak = 0
        previous_status = progress.status
        progress.status = status
        progress.bookmarked = bookmarked
        if status == "mastered":
            progress.review_streak = min(progress.review_streak + 1, 10_000)
            progress.review_interval_days = min(
                60,
                3
                if previous_status != "mastered" or progress.review_interval_days == 0
                else max(3, progress.review_interval_days * 2),
            )
            progress.review_due_at = now + timedelta(days=progress.review_interval_days)
            progress.last_reviewed_at = now
        elif status == "review":
            progress.review_streak = 0
            progress.review_interval_days = 1
            progress.review_due_at = now
            progress.last_reviewed_at = now
        elif status == "learning":
            progress.review_streak = 0
            progress.review_interval_days = 1
            progress.review_due_at = now + timedelta(days=1)
            progress.last_reviewed_at = now
        else:
            progress.review_streak = 0
            progress.review_interval_days = 0
            progress.review_due_at = None
            progress.last_reviewed_at = None
        progress.updated_at = now
        note_record = self._session.scalar(
            select(UserQuestionNoteRecord).where(
                UserQuestionNoteRecord.user_id == user_id,
                UserQuestionNoteRecord.question_id == question_id,
            )
        )
        if not note_record:
            note_record = UserQuestionNoteRecord(
                user_id=user_id, question_id=question_id, updated_at=now
            )
            self._session.add(note_record)
        note_record.content = note
        note_record.updated_at = now
        self._session.commit()
        return UserQuestionState(
            status=status,
            bookmarked=bookmarked,
            note=note,
            review_interval_days=progress.review_interval_days,
            review_streak=progress.review_streak,
            last_reviewed_at=progress.last_reviewed_at,
            review_due_at=progress.review_due_at,
        )

    @staticmethod
    def _summary(record: QuestionRecord) -> QuestionSummary:
        return QuestionSummary(
            id=record.id,
            slug=record.slug,
            title=record.title,
            prompt=record.prompt,
            difficulty=record.difficulty,
            question_type=record.question_type,
            topics=[
                TopicData(id=item.id, slug=item.slug, name=item.name) for item in record.topics
            ],
        )

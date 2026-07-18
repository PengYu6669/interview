from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from interview_copilot.domain.questions import QuestionSetDetail, QuestionSetSummary
from interview_copilot.infrastructure.questions import (
    QuestionRecord,
    QuestionSetItemRecord,
    QuestionSetRecord,
)

from .questions import QuestionBankService


class QuestionSetService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_owned(self, *, user_id: UUID) -> list[QuestionSetSummary]:
        records = self._session.scalars(
            select(QuestionSetRecord)
            .where(QuestionSetRecord.owner_user_id == user_id)
            .options(selectinload(QuestionSetRecord.document))
            .order_by(QuestionSetRecord.updated_at.desc())
        ).all()
        return [self._summary(record) for record in records]

    def get_owned(self, *, user_id: UUID, question_set_id: UUID) -> QuestionSetDetail:
        record = self._session.scalar(
            select(QuestionSetRecord)
            .where(
                QuestionSetRecord.id == question_set_id,
                QuestionSetRecord.owner_user_id == user_id,
            )
            .options(
                selectinload(QuestionSetRecord.document),
                selectinload(QuestionSetRecord.items)
                .selectinload(QuestionSetItemRecord.question)
                .selectinload(QuestionRecord.topics),
            )
        )
        if not record:
            raise LookupError("找不到这个题目集")
        ordered = sorted(record.items, key=lambda item: item.sort_order)
        bank = QuestionBankService(self._session)
        return QuestionSetDetail(
            **self._summary(record).model_dump(),
            questions=[bank._summary(item.question) for item in ordered],
        )

    def create_custom(
        self, *, user_id: UUID, name: str, question_ids: list[UUID]
    ) -> QuestionSetDetail:
        unique_ids = list(dict.fromkeys(question_ids))
        questions = list(
            self._session.scalars(
                select(QuestionRecord)
                .where(
                    QuestionRecord.id.in_(unique_ids),
                    or_(
                        QuestionRecord.published.is_(True),
                        QuestionRecord.owner_user_id == user_id,
                    ),
                )
                .options(selectinload(QuestionRecord.topics))
            )
        )
        by_id = {item.id: item for item in questions}
        if len(by_id) != len(unique_ids):
            raise ValueError("题目集中包含无权访问或不存在的题目")
        now = datetime.now(UTC)
        record = QuestionSetRecord(
            owner_user_id=user_id,
            name=name,
            kind="custom",
            status="ready",
            target_count=len(unique_ids),
            created_at=now,
            updated_at=now,
            items=[
                QuestionSetItemRecord(
                    question_id=question_id,
                    sort_order=index,
                    created_at=now,
                )
                for index, question_id in enumerate(unique_ids, 1)
            ],
        )
        self._session.add(record)
        self._session.commit()
        return self.get_owned(user_id=user_id, question_set_id=record.id)

    def _summary(self, record: QuestionSetRecord) -> QuestionSetSummary:
        question_count = int(
            self._session.scalar(
                select(func.count())
                .select_from(QuestionSetItemRecord)
                .where(QuestionSetItemRecord.question_set_id == record.id)
            )
            or 0
        )
        return QuestionSetSummary(
            id=record.id,
            name=record.name,
            kind=record.kind,
            status=record.status,
            target_count=record.target_count,
            question_count=question_count,
            document_id=record.document_id,
            document_name=record.document.filename if record.document else None,
            knowledge_point_count=(record.document.knowledge_point_count if record.document else 0),
            covered_knowledge_point_count=(
                record.document.covered_knowledge_point_count if record.document else 0
            ),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

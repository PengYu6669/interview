import re
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from interview_copilot.domain.question_content import clean_question_markdown
from interview_copilot.domain.questions import (
    AdminQuestionDetail,
    AdminQuestionSummary,
    QuestionDetail,
    QuestionEvidenceData,
    QuestionSummary,
    SourceData,
    TopicData,
    UserQuestionState,
)
from interview_copilot.infrastructure.database import UserRecord
from interview_copilot.infrastructure.questions import (
    QuestionEvidenceRecord,
    QuestionRecord,
    TopicRecord,
    UserQuestionNoteRecord,
    UserQuestionProgressRecord,
)


class QuestionIndexer(Protocol):
    async def index_question(self, question: QuestionRecord) -> None: ...


class QuestionVisibilityStore(Protocol):
    def set_question_visibility(
        self, *, question_id: UUID, owner_user_id: UUID | None, visibility: str
    ) -> None: ...

    def delete_question(self, *, question_id: UUID) -> None: ...


class QuestionBankService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_questions(self, *, topic: str | None, difficulty: str | None) -> list[QuestionSummary]:
        statement = (
            select(QuestionRecord)
            .where(QuestionRecord.published.is_(True))
            .options(selectinload(QuestionRecord.topics), selectinload(QuestionRecord.document))
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
            .options(selectinload(QuestionRecord.topics), selectinload(QuestionRecord.document))
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
            .options(selectinload(QuestionRecord.topics), selectinload(QuestionRecord.document))
            .order_by(UserQuestionProgressRecord.review_due_at, QuestionRecord.created_at)
        ).all()
        return [self._summary(item) for item in records]

    def get_question(self, slug: str, *, user_id: UUID | None = None) -> QuestionDetail:
        record = self._session.scalar(
            select(QuestionRecord)
            .where(QuestionRecord.slug == slug)
            .options(
                selectinload(QuestionRecord.topics),
                selectinload(QuestionRecord.sources),
                selectinload(QuestionRecord.evidence),
                selectinload(QuestionRecord.document),
            )
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
            evidence=[
                QuestionEvidenceData(
                    section_key=item.section_key,
                    heading_path=list(item.heading_path),
                    quote=item.quote,
                )
                for item in record.evidence
            ],
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
            framework=record.framework,
            source_document_id=record.source_document_id,
            source_document_name=record.source_document_name,
            source_document_version=record.document.version if record.document else None,
        )


class QuestionBankAdminService:
    def __init__(
        self,
        session: Session,
        *,
        indexer: QuestionIndexer | None = None,
        visibility_store: QuestionVisibilityStore | None = None,
    ) -> None:
        self._session = session
        self._indexer = indexer
        self._visibility_store = visibility_store

    @staticmethod
    def _managed_filter():  # type: ignore[no-untyped-def]
        admin_ids = select(UserRecord.id).where(UserRecord.role == "admin")
        return or_(
            QuestionRecord.published.is_(True),
            QuestionRecord.owner_user_id.in_(admin_ids),
        )

    def list_managed(self) -> list[AdminQuestionSummary]:
        records = self._session.scalars(
            select(QuestionRecord)
            .where(self._managed_filter())
            .options(
                selectinload(QuestionRecord.topics),
                selectinload(QuestionRecord.document),
                selectinload(QuestionRecord.evidence),
            )
            .order_by(QuestionRecord.created_at.desc())
        ).all()
        return [self._admin_summary(record) for record in records]

    def get_managed(self, *, question_id: UUID) -> AdminQuestionDetail:
        record = self._managed_record(question_id)
        return self._admin_detail(record)

    async def create_managed(
        self,
        *,
        admin_user_id: UUID,
        title: str,
        prompt: str,
        difficulty: str,
        question_type: str,
        framework: str,
        intent: str,
        answer_outline: list[str],
        common_mistakes: list[str],
        topic_names: list[str],
        content_markdown: str,
    ) -> AdminQuestionDetail:
        now = datetime.now(UTC)
        record = QuestionRecord(
            slug=f"admin-{uuid4().hex}",
            title=title.strip(),
            prompt=prompt.strip(),
            difficulty=difficulty.strip(),
            question_type=question_type.strip(),
            framework=framework.strip(),
            intent=intent.strip(),
            answer_outline=self._clean_items(answer_outline),
            common_mistakes=self._clean_items(common_mistakes),
            content_markdown=clean_question_markdown(content_markdown),
            published=False,
            owner_user_id=admin_user_id,
            created_at=now,
            topics=self._topics(topic_names),
        )
        self._session.add(record)
        self._session.flush()
        if self._indexer:
            await self._indexer.index_question(record)
        self._session.commit()
        return self._admin_detail(self._managed_record(record.id))

    def delete_managed(self, *, question_id: UUID) -> None:
        record = self._managed_record(question_id)
        if self._visibility_store:
            self._visibility_store.delete_question(question_id=record.id)
        self._session.delete(record)
        self._session.commit()

    async def update_managed(
        self,
        *,
        question_id: UUID,
        title: str,
        prompt: str,
        difficulty: str,
        question_type: str,
        framework: str,
        intent: str,
        answer_outline: list[str],
        common_mistakes: list[str],
        topic_names: list[str],
        content_markdown: str,
    ) -> AdminQuestionDetail:
        record = self._managed_record(question_id)
        record.title = title.strip()
        record.prompt = prompt.strip()
        record.difficulty = difficulty.strip()
        record.question_type = question_type.strip()
        record.framework = framework.strip()
        record.intent = intent.strip()
        record.answer_outline = self._clean_items(answer_outline)
        record.common_mistakes = self._clean_items(common_mistakes)
        record.content_markdown = clean_question_markdown(content_markdown)
        record.topics = self._topics(topic_names)
        record.content_fingerprint = sha256(
            f"{record.title.casefold()}\n{record.prompt.casefold()}".encode()
        ).hexdigest()
        if record.published:
            self._validate_publishable(record)
        if self._indexer:
            await self._indexer.index_question(record)
        self._session.commit()
        return self._admin_detail(self._managed_record(question_id))

    def set_publication(
        self, *, admin_user_id: UUID, question_id: UUID, published: bool
    ) -> AdminQuestionSummary:
        record = self._managed_record(question_id)
        if published:
            self._validate_publishable(record)
        if not published and record.owner_user_id is None:
            record.owner_user_id = admin_user_id
        record.published = published
        if self._visibility_store:
            self._visibility_store.set_question_visibility(
                question_id=record.id,
                owner_user_id=record.owner_user_id,
                visibility="public" if published else "private",
            )
        self._session.commit()
        self._session.expire(record, ["evidence"])
        return self._admin_summary(record)

    def _managed_record(self, question_id: UUID) -> QuestionRecord:
        record = self._session.scalar(
            select(QuestionRecord)
            .where(QuestionRecord.id == question_id, self._managed_filter())
            .options(
                selectinload(QuestionRecord.topics),
                selectinload(QuestionRecord.document),
                selectinload(QuestionRecord.evidence),
            )
        )
        if not record:
            raise LookupError("找不到可管理的题目")
        return record

    def _validate_publishable(self, record: QuestionRecord) -> None:
        required = {
            "题目标题": record.title,
            "题干": record.prompt,
            "难度": record.difficulty,
            "题型": record.question_type,
            "考察意图": record.intent,
            "回答框架": record.framework,
        }
        missing = [label for label, value in required.items() if not value.strip()]
        if not record.answer_outline:
            missing.append("答案结构")
        if not record.common_mistakes:
            missing.append("常见错误")
        if not record.topics:
            missing.append("知识点")
        if missing:
            raise ValueError(f"发布前请补全：{'、'.join(missing)}")
        if record.source_document_id:
            evidence_id = self._session.scalar(
                select(QuestionEvidenceRecord.id).where(
                    QuestionEvidenceRecord.question_id == record.id
                )
            )
            if not evidence_id:
                raise ValueError("来源资料生成的题目缺少原文证据，不能发布")

    def _topics(self, names: list[str]) -> list[TopicRecord]:
        topics: list[TopicRecord] = []
        seen: set[str] = set()
        for raw_name in names:
            name = raw_name.strip()
            if not name or name.casefold() in seen:
                continue
            seen.add(name.casefold())
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            if not slug:
                slug = f"topic-{sha256(name.encode()).hexdigest()[:12]}"
            topic = self._session.scalar(select(TopicRecord).where(TopicRecord.slug == slug))
            if not topic:
                topic = TopicRecord(slug=slug, name=name[:100])
                self._session.add(topic)
            topics.append(topic)
        return topics

    @staticmethod
    def _clean_items(items: list[str]) -> list[str]:
        return [item.strip() for item in items if item.strip()]

    @staticmethod
    def _admin_summary(record: QuestionRecord) -> AdminQuestionSummary:
        return AdminQuestionSummary(
            **QuestionBankService._summary(record).model_dump(),
            published=record.published,
            owner_user_id=record.owner_user_id,
            evidence_count=len(record.evidence),
            created_at=record.created_at,
        )

    @staticmethod
    def _admin_detail(record: QuestionRecord) -> AdminQuestionDetail:
        return AdminQuestionDetail(
            **QuestionBankAdminService._admin_summary(record).model_dump(),
            intent=record.intent,
            answer_outline=record.answer_outline,
            common_mistakes=record.common_mistakes,
            content_markdown=record.content_markdown,
            evidence=[
                QuestionEvidenceData(
                    section_key=item.section_key,
                    heading_path=list(item.heading_path),
                    quote=item.quote,
                )
                for item in record.evidence
            ],
        )

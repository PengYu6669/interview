import re
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from interview_copilot.domain.questions import (
    CitationData,
    QuestionChatAnswer,
    QuestionChatHistory,
    QuestionChatMessageData,
    QuestionImportResult,
)
from interview_copilot.domain.retrieval import RagDocumentInput
from interview_copilot.infrastructure.questions import (
    QuestionConversationRecord,
    QuestionMessageRecord,
    QuestionRecord,
    TopicRecord,
)
from interview_copilot.providers.deepseek_question_bank import DeepSeekQuestionBankProvider

from .questions import QuestionBankService
from .retrieval.indexing import RagIndexingService
from .retrieval.search import RagSearchService


class QuestionWorkflowService:
    def __init__(
        self,
        session: Session,
        *,
        deepseek: DeepSeekQuestionBankProvider | None = None,
        rag_indexing: RagIndexingService | None = None,
        rag_search: RagSearchService | None = None,
    ) -> None:
        self._session = session
        self._deepseek = deepseek
        self._rag_indexing = rag_indexing
        self._rag_search = rag_search

    async def import_document(
        self, *, user_id: UUID, filename: str, text: str
    ) -> QuestionImportResult:
        generated = await self._deepseek_provider().generate_questions(text)
        details = []
        for item in generated.questions:
            topics = []
            for name in item.topics:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                if not slug:
                    slug = f"topic-{sha256(name.encode('utf-8')).hexdigest()[:12]}"
                topic = self._session.scalar(select(TopicRecord).where(TopicRecord.slug == slug))
                if not topic:
                    topic = TopicRecord(slug=slug, name=name[:100])
                    self._session.add(topic)
                topics.append(topic)
            question = QuestionRecord(
                slug=f"user-{uuid4().hex}",
                title=item.title,
                prompt=item.prompt,
                difficulty=item.difficulty,
                question_type=item.question_type,
                intent=item.intent,
                answer_outline=item.answer_outline,
                common_mistakes=item.common_mistakes,
                published=False,
                created_at=datetime.now(UTC),
                owner_user_id=user_id,
                content_markdown=item.content_markdown,
                source_document_name=filename,
                topics=topics,
            )
            self._session.add(question)
            self._session.flush()
            await self.index_question(question)
            details.append(QuestionBankService(self._session)._detail(question, editable=True))
        self._session.commit()
        return QuestionImportResult(questions=details, warnings=generated.warnings)

    async def update_owned(
        self, *, user_id: UUID, question_id: UUID, title: str, content_markdown: str
    ) -> None:
        question = self._session.scalar(
            select(QuestionRecord)
            .where(QuestionRecord.id == question_id, QuestionRecord.owner_user_id == user_id)
            .options(selectinload(QuestionRecord.topics), selectinload(QuestionRecord.sources))
        )
        if not question:
            raise LookupError("找不到可编辑的个人题目")
        question.title = title
        question.content_markdown = content_markdown
        await self.index_question(question)
        self._session.commit()

    async def index_question(self, question: QuestionRecord) -> None:
        if not self._rag_indexing:
            raise RuntimeError("题库 RAG 索引服务尚未配置")
        await self._rag_indexing.index(
            RagDocumentInput(
                owner_user_id=question.owner_user_id,
                corpus_type="knowledge",
                source_type="question",
                source_id=question.id,
                visibility="public" if question.published else "private",
                title=question.source_document_name or question.title,
                text=question.content_markdown or question.prompt,
                metadata={"question_id": str(question.id), "slug": question.slug},
            )
        )

    def get_chat_history(
        self, *, user_id: UUID, question_id: UUID
    ) -> QuestionChatHistory | None:
        self._question(user_id=user_id, question_id=question_id)
        conversation = self._session.scalar(
            select(QuestionConversationRecord)
            .where(
                QuestionConversationRecord.user_id == user_id,
                QuestionConversationRecord.question_id == question_id,
            )
            .order_by(QuestionConversationRecord.created_at.desc())
            .limit(1)
        )
        if not conversation:
            return None
        messages = self._conversation_messages(conversation.id)
        return QuestionChatHistory(
            conversation_id=conversation.id,
            messages=[
                QuestionChatMessageData(
                    role=message.role,
                    content=message.content,
                    citations=[CitationData.model_validate(item) for item in message.citations],
                    created_at=message.created_at,
                )
                for message in messages
            ],
        )

    async def chat(
        self,
        *,
        user_id: UUID,
        question_id: UUID,
        message: str,
        conversation_id: UUID | None = None,
    ) -> QuestionChatAnswer:
        self._question(user_id=user_id, question_id=question_id)
        conversation = (
            self._owned_conversation(
                user_id=user_id,
                question_id=question_id,
                conversation_id=conversation_id,
            )
            if conversation_id
            else None
        )
        history_rows = self._conversation_messages(conversation.id)[-8:] if conversation else []
        if not self._rag_search:
            raise RuntimeError("题库 RAG 检索服务尚未配置")
        evidence = await self._rag_search.search(
            user_id=user_id,
            query=message,
            corpus_types=["knowledge"],
            source_types=["question"],
            source_ids=[question_id],
            limit=5,
        )
        if not evidence:
            question = self._question(user_id=user_id, question_id=question_id)
            await self.index_question(question)
            evidence = await self._rag_search.search(
                user_id=user_id,
                query=message,
                corpus_types=["knowledge"],
                source_types=["question"],
                source_ids=[question_id],
                limit=5,
            )
        if not evidence:
            raise LookupError("这道题没有达到相关度要求的学习资料")
        answer = await self._deepseek_provider().answer(
            question=message,
            evidence=[item.content for item in evidence],
            history=[{"role": item.role, "content": item.content} for item in history_rows],
        )
        if not conversation:
            conversation = QuestionConversationRecord(
                user_id=user_id, question_id=question_id, created_at=datetime.now(UTC)
            )
            self._session.add(conversation)
            self._session.flush()
        citations = [
            CitationData(
                index=index,
                title=evidence[index - 1].title,
                url=None,
                quote=evidence[index - 1].content[:500],
            )
            for index in answer.citation_indexes
        ]
        now = datetime.now(UTC)
        self._session.add_all(
            [
                QuestionMessageRecord(
                    conversation_id=conversation.id,
                    role="user",
                    content=message,
                    citations=[],
                    created_at=now,
                ),
                QuestionMessageRecord(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=answer.answer_markdown,
                    citations=[item.model_dump(mode="json") for item in citations],
                    created_at=now,
                ),
            ]
        )
        self._session.commit()
        return QuestionChatAnswer(
            answer_markdown=answer.answer_markdown,
            citations=citations,
            conversation_id=conversation.id,
        )

    def _question(self, *, user_id: UUID, question_id: UUID) -> QuestionRecord:
        question = self._session.get(QuestionRecord, question_id)
        if not question or (not question.published and question.owner_user_id != user_id):
            raise LookupError("找不到这道题目")
        return question

    def _owned_conversation(
        self, *, user_id: UUID, question_id: UUID, conversation_id: UUID
    ) -> QuestionConversationRecord:
        conversation = self._session.scalar(
            select(QuestionConversationRecord).where(
                QuestionConversationRecord.id == conversation_id,
                QuestionConversationRecord.user_id == user_id,
                QuestionConversationRecord.question_id == question_id,
            )
        )
        if not conversation:
            raise LookupError("找不到这段题库对话")
        return conversation

    def _conversation_messages(self, conversation_id: UUID) -> list[QuestionMessageRecord]:
        return list(
            self._session.scalars(
                select(QuestionMessageRecord)
                .where(QuestionMessageRecord.conversation_id == conversation_id)
                .order_by(QuestionMessageRecord.created_at, QuestionMessageRecord.id)
            ).all()
        )

    def _deepseek_provider(self) -> DeepSeekQuestionBankProvider:
        if not self._deepseek:
            raise RuntimeError("题库 AI 服务尚未配置")
        return self._deepseek

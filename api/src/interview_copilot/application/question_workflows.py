import re
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from interview_copilot.application.retrieval.chunking import split_semantic_chunks
from interview_copilot.domain.questions import (
    CitationData,
    QuestionChatAnswer,
    QuestionChatHistory,
    QuestionChatMessageData,
    QuestionDocumentSummary,
    QuestionImportResult,
)
from interview_copilot.domain.retrieval import RagDocumentInput
from interview_copilot.infrastructure.questions import (
    QuestionConversationRecord,
    QuestionDocumentRecord,
    QuestionEvidenceRecord,
    QuestionMessageRecord,
    QuestionRecord,
    TopicRecord,
)
from interview_copilot.infrastructure.rag import RagDocumentRecord
from interview_copilot.providers.deepseek_question_bank import (
    DeepSeekQuestionBankProvider,
    QuestionGenerationSection,
)

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
        self,
        *,
        user_id: UUID,
        filename: str,
        media_type: str,
        text: str,
        initial_warnings: list[str] | None = None,
        force_new_version: bool = False,
    ) -> QuestionImportResult:
        if len(text) > 200_000:
            raise ValueError("资料提取文本不能超过 20 万字符，请拆分后导入")
        content_hash = sha256(text.encode("utf-8")).hexdigest()
        existing = self._session.scalar(
            select(QuestionDocumentRecord)
            .where(
                QuestionDocumentRecord.owner_user_id == user_id,
                QuestionDocumentRecord.content_hash == content_hash,
                QuestionDocumentRecord.status == "ready",
            )
            .order_by(QuestionDocumentRecord.version.desc())
        )
        if existing and not force_new_version:
            result = self._document_result(existing)
            result.warnings.insert(0, "相同内容已经导入，已返回现有题库版本")
            return result
        version = int(
            self._session.scalar(
                select(func.coalesce(func.max(QuestionDocumentRecord.version), 0)).where(
                    QuestionDocumentRecord.owner_user_id == user_id,
                    QuestionDocumentRecord.filename == filename,
                )
            )
            or 0
        ) + 1
        now = datetime.now(UTC)
        provider = self._deepseek_provider()
        document = QuestionDocumentRecord(
            owner_user_id=user_id,
            filename=filename,
            media_type=media_type,
            normalized_text=text,
            content_hash=content_hash,
            version=version,
            status="processing",
            warnings=list(initial_warnings or []),
            coverage_ratio=0,
            section_count=0,
            covered_section_count=0,
            model=provider.model_name,
            prompt_version=provider.prompt_version,
            created_at=now,
            updated_at=now,
        )
        self._session.add(document)
        self._session.flush()
        if not self._rag_indexing:
            raise RuntimeError("题库 RAG 索引服务尚未配置")
        await self._rag_indexing.index(
            RagDocumentInput(
                owner_user_id=user_id,
                corpus_type="knowledge",
                source_type="question_document",
                source_id=document.id,
                visibility="private",
                title=f"{filename} · v{version}",
                text=text,
                metadata={"document_id": str(document.id), "version": version},
            )
        )
        chunks = split_semantic_chunks(
            text, target_tokens=1_000, max_tokens=1_600, overlap_tokens=0
        )
        sections = [
            QuestionGenerationSection(
                key=f"section-{chunk.index}",
                heading_path=list(chunk.heading_path),
                content=chunk.content,
            )
            for chunk in chunks
        ]
        generated_batches = []
        for offset in range(0, len(sections), 4):
            batch = sections[offset : offset + 4]
            generated_batches.append(
                await provider.generate_questions(
                    batch,
                    desired_questions=min(8, max(2, len(batch) * 2)),
                )
            )
        section_map = {item.key: item for item in sections}
        generated_questions = [
            item for batch in generated_batches for item in batch.questions
        ]
        generated_warnings = [
            warning for batch in generated_batches for warning in batch.warnings
        ]
        details = []
        fingerprints: set[str] = set()
        covered_sections: set[str] = set()
        for item in generated_questions:
            fingerprint = sha256(
                f"{item.title.strip().casefold()}\n{item.prompt.strip().casefold()}".encode()
            ).hexdigest()
            if fingerprint in fingerprints:
                generated_warnings.append(f"重复题目“{item.title}”已跳过")
                continue
            fingerprints.add(fingerprint)
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
                source_document_id=document.id,
                document=document,
                framework=item.framework,
                content_fingerprint=fingerprint,
                topics=topics,
            )
            self._session.add(question)
            self._session.flush()
            for evidence in item.evidence:
                section = section_map[evidence.section_key]
                covered_sections.add(evidence.section_key)
                question.evidence.append(
                    QuestionEvidenceRecord(
                        document_id=document.id,
                        section_key=evidence.section_key,
                        heading_path=section.heading_path,
                        quote=evidence.quote,
                    )
                )
            await self.index_question(question)
            details.append(QuestionBankService(self._session)._detail(question, editable=True))
        if not details:
            raise RuntimeError("资料没有生成可保存的题目")
        uncovered = [item.key for item in sections if item.key not in covered_sections]
        document.section_count = len(sections)
        document.covered_section_count = len(covered_sections)
        document.coverage_ratio = len(covered_sections) / len(sections) if sections else 0
        document.status = "ready"
        document.warnings = [
            *list(initial_warnings or []),
            *generated_warnings,
            *(
                [f"仍有 {len(uncovered)} 个资料片段未形成题目，可使用重新生成补充"]
                if uncovered
                else []
            ),
        ]
        document.updated_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(document)
        return QuestionImportResult(
            document=self._document_summary(document, question_count=len(details)),
            questions=details,
            warnings=list(document.warnings),
        )

    def list_documents(self, *, user_id: UUID) -> list[QuestionDocumentSummary]:
        documents = self._session.scalars(
            select(QuestionDocumentRecord)
            .where(QuestionDocumentRecord.owner_user_id == user_id)
            .order_by(QuestionDocumentRecord.updated_at.desc())
        ).all()
        return [
            self._document_summary(
                item,
                question_count=int(
                    self._session.scalar(
                        select(func.count())
                        .select_from(QuestionRecord)
                        .where(QuestionRecord.source_document_id == item.id)
                    )
                    or 0
                ),
            )
            for item in documents
        ]

    async def regenerate_document(
        self, *, user_id: UUID, document_id: UUID
    ) -> QuestionImportResult:
        document = self._owned_document(user_id=user_id, document_id=document_id)
        return await self.import_document(
            user_id=user_id,
            filename=document.filename,
            media_type=document.media_type,
            text=document.normalized_text,
            initial_warnings=[f"基于 v{document.version} 重新生成"],
            force_new_version=True,
        )

    def delete_document(self, *, user_id: UUID, document_id: UUID) -> None:
        document = self._owned_document(user_id=user_id, document_id=document_id)
        self._session.execute(
            delete(RagDocumentRecord).where(
                RagDocumentRecord.owner_user_id == user_id,
                RagDocumentRecord.source_type == "question_document",
                RagDocumentRecord.source_id == document.id,
            )
        )
        self._session.delete(document)
        self._session.commit()

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
                metadata={
                    "question_id": str(question.id),
                    "slug": question.slug,
                    "document_id": (
                        str(question.source_document_id)
                        if question.source_document_id
                        else None
                    ),
                },
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
        question = self._question(user_id=user_id, question_id=question_id)
        source_type = "question_document" if question.source_document_id else "question"
        source_id = question.source_document_id or question.id
        evidence = await self._rag_search.search(
            user_id=user_id,
            query=message,
            corpus_types=["knowledge"],
            source_types=[source_type],
            source_ids=[source_id],
            limit=5,
        )
        if not evidence:
            if question.source_document_id:
                raise LookupError("这道题的原始资料尚未完成检索索引")
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
        question = self._session.scalar(
            select(QuestionRecord)
            .where(QuestionRecord.id == question_id)
            .options(selectinload(QuestionRecord.evidence))
        )
        if not question or (not question.published and question.owner_user_id != user_id):
            raise LookupError("找不到这道题目")
        return question

    def _owned_document(
        self, *, user_id: UUID, document_id: UUID
    ) -> QuestionDocumentRecord:
        document = self._session.scalar(
            select(QuestionDocumentRecord).where(
                QuestionDocumentRecord.id == document_id,
                QuestionDocumentRecord.owner_user_id == user_id,
            )
        )
        if not document:
            raise LookupError("找不到这份题库资料")
        return document

    def _document_result(self, document: QuestionDocumentRecord) -> QuestionImportResult:
        questions = self._session.scalars(
            select(QuestionRecord)
            .where(QuestionRecord.source_document_id == document.id)
            .options(
                selectinload(QuestionRecord.topics),
                selectinload(QuestionRecord.sources),
                selectinload(QuestionRecord.evidence),
                selectinload(QuestionRecord.document),
            )
            .order_by(QuestionRecord.created_at)
        ).all()
        details = [
            QuestionBankService(self._session)._detail(item, editable=True)
            for item in questions
        ]
        return QuestionImportResult(
            document=self._document_summary(document, question_count=len(details)),
            questions=details,
            warnings=list(document.warnings),
        )

    @staticmethod
    def _document_summary(
        document: QuestionDocumentRecord, *, question_count: int
    ) -> QuestionDocumentSummary:
        return QuestionDocumentSummary(
            id=document.id,
            filename=document.filename,
            media_type=document.media_type,
            version=document.version,
            status=document.status,
            warnings=list(document.warnings),
            coverage_ratio=document.coverage_ratio,
            section_count=document.section_count,
            covered_section_count=document.covered_section_count,
            question_count=question_count,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

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

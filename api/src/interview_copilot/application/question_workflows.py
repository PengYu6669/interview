import asyncio
import re
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from interview_copilot.application.retrieval.chunking import split_semantic_chunks
from interview_copilot.domain.questions import (
    CitationData,
    QuestionChatAnswer,
    QuestionChatHistory,
    QuestionChatMessageData,
    QuestionDetail,
    QuestionDocumentSummary,
    QuestionImportResult,
)
from interview_copilot.domain.retrieval import RagDocumentInput
from interview_copilot.infrastructure.questions import (
    KnowledgePointRecord,
    QuestionConversationRecord,
    QuestionDocumentRecord,
    QuestionEvidenceRecord,
    QuestionMessageRecord,
    QuestionRecord,
    QuestionSetItemRecord,
    QuestionSetRecord,
    TopicRecord,
)
from interview_copilot.infrastructure.rag import RagDocumentRecord
from interview_copilot.providers.deepseek_question_bank import (
    DeepSeekQuestionBankProvider,
    GeneratedQuestions,
    KnowledgePointCandidate,
    KnowledgePointMap,
    QuestionGenerationSection,
)

from .questions import QuestionBankService
from .retrieval.indexing import RagIndexingService
from .retrieval.search import RagSearchService

_QUESTION_ANCHOR = re.compile(
    r"^(?:Q\s*\d{1,4}|问题\s*\d{1,4}|第\s*\d{1,4}\s*[题问])\s*[：:.、-]?\s*(.+)$",
    re.IGNORECASE,
)


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
        progress: Callable[[str, int, UUID | None], None] | None = None,
        question_limit: int = 30,
    ) -> QuestionImportResult:
        if len(text) > 200_000:
            raise ValueError("资料提取文本不能超过 20 万字符，请拆分后导入")
        if not 10 <= question_limit <= 100:
            raise ValueError("题目上限必须在 10 到 100 之间")
        provider = self._deepseek_provider()
        content_hash = sha256(text.encode("utf-8")).hexdigest()
        existing = self._session.scalar(
            select(QuestionDocumentRecord)
            .where(
                QuestionDocumentRecord.owner_user_id == user_id,
                QuestionDocumentRecord.content_hash == content_hash,
                QuestionDocumentRecord.status == "ready",
                QuestionDocumentRecord.prompt_version == provider.prompt_version,
            )
            .order_by(QuestionDocumentRecord.version.desc())
        )
        if existing and not force_new_version:
            result = self._document_result(existing)
            result.warnings.insert(0, "相同内容已经导入，已返回现有题库版本")
            return result
        version = (
            int(
                self._session.scalar(
                    select(func.coalesce(func.max(QuestionDocumentRecord.version), 0)).where(
                        QuestionDocumentRecord.owner_user_id == user_id,
                        QuestionDocumentRecord.filename == filename,
                    )
                )
                or 0
            )
            + 1
        )
        now = datetime.now(UTC)
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
            knowledge_point_count=0,
            covered_knowledge_point_count=0,
            requested_question_limit=question_limit,
            model=provider.model_name,
            prompt_version=provider.prompt_version,
            created_at=now,
            updated_at=now,
        )
        self._session.add(document)
        self._session.flush()
        question_set = QuestionSetRecord(
            owner_user_id=user_id,
            document_id=document.id,
            name=filename,
            kind="default",
            status="generating",
            target_count=question_limit,
            created_at=now,
            updated_at=now,
        )
        self._session.add(question_set)
        self._session.flush()
        if progress:
            progress("正在建立资料索引", 25, document.id)
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
        chunks = split_semantic_chunks(text, target_tokens=650, max_tokens=900, overlap_tokens=100)
        sections = [
            QuestionGenerationSection(
                key=f"section-{chunk.index}",
                heading_path=list(chunk.heading_path),
                content=chunk.content,
            )
            for chunk in chunks
        ]
        if progress:
            progress("正在抽取知识点地图", 38, document.id)
        candidate_points: list[KnowledgePointCandidate] = []
        section_batches = [sections[offset : offset + 12] for offset in range(0, len(sections), 12)]
        semaphore = asyncio.Semaphore(3)

        async def extract_batch(
            batch: list[QuestionGenerationSection],
        ) -> KnowledgePointMap:
            async with semaphore:
                return await provider.extract_knowledge_points(batch)

        point_maps = await asyncio.gather(*(extract_batch(batch) for batch in section_batches))
        for batch_number, point_map in enumerate(point_maps, 1):
            candidate_points.extend(point_map.knowledge_points)
            if progress:
                progress(
                    f"正在分析知识点 {batch_number}/{len(section_batches)}",
                    30 + round(20 * batch_number / len(section_batches)),
                    document.id,
                )
        merge_warning: str | None = None
        if len(sections) > 12:
            try:
                merged_map = await provider.merge_knowledge_points(candidate_points)
            except RuntimeError as exc:
                merged_map = KnowledgePointMap(
                    knowledge_points=provider._dedupe_points(candidate_points),
                    warnings=[f"知识点全局合并失败，已使用分批结果继续生成：{exc}"],
                )
                merge_warning = merged_map.warnings[0]
        else:
            merged_map = point_map
        structural_points = self._structural_points(sections)
        merged_map = merged_map.model_copy(
            update={
                "knowledge_points": self._preserve_structural_points(
                    merged_map.knowledge_points, structural_points
                )
            }
        )
        section_map = {item.key: item for item in sections}
        point_records: dict[str, KnowledgePointRecord] = {}
        for point in merged_map.knowledge_points:
            record = KnowledgePointRecord(
                document_id=document.id,
                stable_key=point.stable_key,
                title=point.title,
                knowledge_type=point.knowledge_type,
                interview_claim=point.interview_claim,
                section_keys=point.section_keys,
                heading_paths=[list(section_map[key].heading_path) for key in point.section_keys],
                created_at=now,
            )
            self._session.add(record)
            point_records[point.stable_key] = record
        document.knowledge_point_count = len(point_records)
        desired_total = min(question_limit, int(len(point_records) * 1.2))
        generation_plan = self._question_plan(
            merged_map.knowledge_points,
            desired_total,
            priority_keys={point.stable_key for point in structural_points},
        )
        generated_batches = []
        generated_warnings: list[str] = []
        if merge_warning:
            generated_warnings.append(merge_warning)
        point_batches = [
            generation_plan[offset : offset + 4] for offset in range(0, len(generation_plan), 4)
        ]
        batch_count = len(point_batches)

        async def generate_batch(
            batch_number: int,
            batch_plan: list[tuple[KnowledgePointCandidate, int]],
        ) -> tuple[int, GeneratedQuestions]:
            batch_points = [
                point.model_copy(update={"section_keys": point.section_keys[:1]})
                for point, _ in batch_plan
            ]
            batch_section_keys = {key for point in batch_points for key in point.section_keys}
            batch = [section_map[key] for key in batch_section_keys]
            async with semaphore:
                return batch_number, await provider.generate_questions(
                    batch,
                    desired_questions=sum(count for _, count in batch_plan),
                    knowledge_points=batch_points,
                )

        batch_results = await asyncio.gather(
            *(
                generate_batch(batch_number, batch_plan)
                for batch_number, batch_plan in enumerate(point_batches, 1)
            ),
            return_exceptions=True,
        )
        for completed, batch_result in enumerate(batch_results, 1):
            if isinstance(batch_result, BaseException):
                generated_warnings.append(
                    f"第 {completed}/{batch_count} 批题目生成失败，已跳过：{batch_result}"
                )
            else:
                _, generated = batch_result
                generated_batches.append(generated)
            if progress:
                generated_count = sum(len(batch.questions) for batch in generated_batches)
                progress(
                    f"正在生成题目 {generated_count}/{desired_total}",
                    55 + round(35 * completed / batch_count),
                    document.id,
                )
        generated_questions = [item for batch in generated_batches for item in batch.questions]
        generated_warnings.extend(
            warning for batch in generated_batches for warning in batch.warnings
        )
        details: list[QuestionDetail] = []
        fingerprints: set[str] = set()
        covered_sections: set[str] = set()
        saved_point_keys: set[str] = set()
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
                knowledge_point=point_records.get(item.knowledge_point_key),
                framework=item.framework,
                content_fingerprint=fingerprint,
                topics=topics,
            )
            self._session.add(question)
            self._session.flush()
            question_set.items.append(
                QuestionSetItemRecord(
                    question_id=question.id,
                    sort_order=len(details) + 1,
                    created_at=datetime.now(UTC),
                )
            )
            if item.knowledge_point_key in point_records:
                saved_point_keys.add(item.knowledge_point_key)
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
            failures = "；".join(generated_warnings[:3])
            raise RuntimeError(f"资料没有生成可保存的题目：{failures}")
        minimum_acceptable = min(
            desired_total,
            max(len(structural_points), max(1, int(desired_total * 0.7))),
        )
        if len(details) < minimum_acceptable:
            raise RuntimeError(
                f"题目生成质量未达标：计划 {desired_total} 道，仅生成 {len(details)} 道；"
                "请重试或检查资料清洗提示"
            )
        document.section_count = len(sections)
        document.covered_section_count = len(covered_sections)
        document.covered_knowledge_point_count = len(saved_point_keys)
        document.coverage_ratio = len(saved_point_keys) / len(point_records) if point_records else 0
        document.status = "ready"
        question_set.status = "ready"
        question_set.updated_at = datetime.now(UTC)
        document.warnings = [
            *list(initial_warnings or []),
            *generated_warnings,
            *(
                [
                    f"仍有 {len(point_records) - len(saved_point_keys)} 个知识点未形成题目，"
                    "可使用继续生成补充"
                ]
                if len(saved_point_keys) < len(point_records)
                else []
            ),
        ]
        document.updated_at = datetime.now(UTC)
        if progress:
            progress("正在保存题目与原文证据", 92, document.id)
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
        self, *, user_id: UUID, document_id: UUID, additional_limit: int = 30
    ) -> QuestionImportResult:
        document = self._owned_document(user_id=user_id, document_id=document_id)
        if not 10 <= additional_limit <= 30:
            raise ValueError("单次继续生成数量必须在 10 到 30 之间")
        points = list(
            self._session.scalars(
                select(KnowledgePointRecord)
                .where(
                    KnowledgePointRecord.document_id == document.id,
                    ~select(QuestionRecord.id)
                    .where(QuestionRecord.knowledge_point_id == KnowledgePointRecord.id)
                    .exists(),
                )
                .order_by(KnowledgePointRecord.created_at)
            )
        )
        if not points:
            raise ValueError("这份资料的知识点已经全部生成题目")
        question_set = self._session.scalar(
            select(QuestionSetRecord).where(
                QuestionSetRecord.document_id == document.id,
                QuestionSetRecord.owner_user_id == user_id,
                QuestionSetRecord.kind == "default",
            )
        )
        if not question_set:
            raise RuntimeError("这份资料缺少默认题目集")
        existing_set_count = len(question_set.items)
        chunks = split_semantic_chunks(
            document.normalized_text,
            target_tokens=1_000,
            max_tokens=1_600,
            overlap_tokens=0,
        )
        section_map = {
            f"section-{chunk.index}": QuestionGenerationSection(
                key=f"section-{chunk.index}",
                heading_path=list(chunk.heading_path),
                content=chunk.content,
            )
            for chunk in chunks
        }
        candidates = [
            KnowledgePointCandidate(
                stable_key=point.stable_key,
                title=point.title,
                knowledge_type=cast(
                    Literal[
                        "概念",
                        "机制",
                        "对比",
                        "场景",
                        "架构",
                        "算法",
                        "项目",
                        "行为",
                        "取舍",
                    ],
                    point.knowledge_type
                    if point.knowledge_type
                    in {"概念", "机制", "对比", "场景", "架构", "算法", "项目", "行为", "取舍"}
                    else "概念",
                ),
                interview_claim=point.interview_claim,
                section_keys=point.section_keys,
            )
            for point in points
        ]
        plan = self._question_plan(candidates, min(additional_limit, len(candidates)))
        point_records = {point.stable_key: point for point in points}
        provider = self._deepseek_provider()
        generated = []
        warnings = list(document.warnings)
        for offset in range(0, len(plan), 4):
            batch_plan = plan[offset : offset + 4]
            batch_points = [
                point.model_copy(update={"section_keys": point.section_keys[:1]})
                for point, _ in batch_plan
            ]
            sections = [section_map[point.section_keys[0]] for point in batch_points]
            try:
                result = await provider.generate_questions(
                    sections,
                    desired_questions=sum(count for _, count in batch_plan),
                    knowledge_points=batch_points,
                )
                generated.extend(result.questions)
                warnings.extend(result.warnings)
            except RuntimeError as exc:
                warnings.append(f"继续生成批次失败，已跳过：{exc}")
        details: list[QuestionDetail] = []
        existing_fingerprints = set(
            self._session.scalars(
                select(QuestionRecord.content_fingerprint).where(
                    QuestionRecord.source_document_id == document.id,
                    QuestionRecord.content_fingerprint.is_not(None),
                )
            )
        )
        for item in generated:
            fingerprint = sha256(
                f"{item.title.strip().casefold()}\n{item.prompt.strip().casefold()}".encode()
            ).hexdigest()
            if fingerprint in existing_fingerprints:
                continue
            existing_fingerprints.add(fingerprint)
            topics = []
            for name in item.topics:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                slug = slug or f"topic-{sha256(name.encode('utf-8')).hexdigest()[:12]}"
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
                source_document_name=document.filename,
                document=document,
                knowledge_point=point_records[item.knowledge_point_key],
                framework=item.framework,
                content_fingerprint=fingerprint,
                topics=topics,
            )
            self._session.add(question)
            self._session.flush()
            question_set.items.append(
                QuestionSetItemRecord(
                    question_id=question.id,
                    sort_order=existing_set_count + len(details) + 1,
                    created_at=datetime.now(UTC),
                )
            )
            for evidence in item.evidence:
                section = section_map[evidence.section_key]
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
            raise RuntimeError("未能生成新的非重复题目")
        covered_count = int(
            self._session.scalar(
                select(func.count(func.distinct(QuestionRecord.knowledge_point_id))).where(
                    QuestionRecord.source_document_id == document.id,
                    QuestionRecord.knowledge_point_id.is_not(None),
                )
            )
            or 0
        )
        document.covered_knowledge_point_count = covered_count
        document.coverage_ratio = covered_count / document.knowledge_point_count
        document.warnings = warnings
        document.updated_at = datetime.now(UTC)
        question_set.status = "ready"
        question_set.target_count += additional_limit
        question_set.updated_at = datetime.now(UTC)
        self._session.commit()
        return QuestionImportResult(
            document=self._document_summary(
                document,
                question_count=int(
                    self._session.scalar(
                        select(func.count())
                        .select_from(QuestionRecord)
                        .where(QuestionRecord.source_document_id == document.id)
                    )
                    or 0
                ),
            ),
            questions=details,
            warnings=warnings,
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
                        str(question.source_document_id) if question.source_document_id else None
                    ),
                },
            )
        )

    def get_chat_history(self, *, user_id: UUID, question_id: UUID) -> QuestionChatHistory | None:
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

    def _owned_document(self, *, user_id: UUID, document_id: UUID) -> QuestionDocumentRecord:
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
            QuestionBankService(self._session)._detail(item, editable=True) for item in questions
        ]
        return QuestionImportResult(
            document=self._document_summary(document, question_count=len(details)),
            questions=details,
            warnings=list(document.warnings),
        )

    @staticmethod
    def _structural_points(
        sections: list[QuestionGenerationSection],
    ) -> list[KnowledgePointCandidate]:
        anchors: dict[str, tuple[str, list[str]]] = {}
        for section in sections:
            content_headings = [
                line.removeprefix("##").strip()
                for line in section.content.splitlines()
                if line.startswith("## ")
            ]
            for heading in [*section.heading_path, *content_headings]:
                match = _QUESTION_ANCHOR.match(heading.strip())
                if not match:
                    continue
                title = match.group(1).strip() or heading.strip()
                normalized = re.sub(r"\s+", "", title).casefold()
                if normalized in anchors:
                    anchors[normalized][1].append(section.key)
                else:
                    anchors[normalized] = (title, [section.key])
        return [
            KnowledgePointCandidate(
                stable_key=f"document-anchor-{sha256(key.encode()).hexdigest()[:16]}",
                title=title,
                knowledge_type="场景",
                interview_claim=f"围绕“{title}”给出明确结论、依据和边界。",
                section_keys=list(dict.fromkeys(section_keys))[:12],
            )
            for key, (title, section_keys) in anchors.items()
        ]

    @staticmethod
    def _preserve_structural_points(
        model_points: list[KnowledgePointCandidate],
        structural_points: list[KnowledgePointCandidate],
    ) -> list[KnowledgePointCandidate]:
        result = list(structural_points)
        normalized_titles = {
            re.sub(r"\s+", "", point.title).casefold() for point in structural_points
        }
        for point in model_points:
            normalized = re.sub(r"\s+", "", point.title).casefold()
            if normalized not in normalized_titles:
                result.append(point)
                normalized_titles.add(normalized)
        return result[:100]

    @staticmethod
    def _question_plan(
        points: list[KnowledgePointCandidate],
        desired_total: int,
        *,
        priority_keys: set[str] | None = None,
    ) -> list[tuple[KnowledgePointCandidate, int]]:
        if desired_total <= 0:
            return []
        weights = {
            "概念": 0.40,
            "机制": 0.20,
            "对比": 0.15,
            "场景": 0.15,
            "架构": 0.02,
            "算法": 0.02,
            "项目": 0.02,
            "行为": 0.02,
            "取舍": 0.02,
        }
        type_order = list(weights)
        priority_keys = priority_keys or set()
        selected = [point for point in points if point.stable_key in priority_keys][:desired_total]
        selected_keys = {point.stable_key for point in selected}
        remaining = [point for point in points if point.stable_key not in selected_keys]
        grouped = {
            name: [point for point in remaining if point.knowledge_type == name]
            for name in type_order
        }
        selection_total = min(desired_total, len(points))
        available_types = [name for name in type_order if grouped[name]]
        normalized_total = sum(weights[name] for name in available_types)
        remaining_slots = selection_total - len(selected)
        targets = (
            {
                name: min(
                    len(grouped[name]),
                    int(remaining_slots * weights[name] / normalized_total),
                )
                for name in available_types
            }
            if normalized_total
            else {}
        )
        for name in available_types:
            selected.extend(grouped[name][: targets[name]])
            grouped[name] = grouped[name][targets[name] :]
        while len(selected) < selection_total:
            candidates = [name for name in available_types if grouped[name]]
            if not candidates:
                break
            name = max(candidates, key=lambda item: weights[item])
            selected.append(grouped[name].pop(0))
        counts = [1] * len(selected)
        for index in range(desired_total - len(selected)):
            counts[index % len(counts)] += 1
        return list(zip(selected, counts, strict=True))

    @staticmethod
    def _document_summary(
        document: QuestionDocumentRecord, *, question_count: int
    ) -> QuestionDocumentSummary:
        suggested = min(30, int(document.knowledge_point_count * 1.2))
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
            knowledge_point_count=document.knowledge_point_count,
            covered_knowledge_point_count=document.covered_knowledge_point_count,
            suggested_question_count=suggested,
            requested_question_limit=document.requested_question_limit,
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

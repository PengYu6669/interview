import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from interview_copilot.application.question_workflows import QuestionWorkflowService
from interview_copilot.application.questions import QuestionBankService
from interview_copilot.domain.retrieval import RetrievedEvidence
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.questions import (
    QuestionConversationRecord,
    QuestionMessageRecord,
    QuestionRecord,
    TopicRecord,
)
from interview_copilot.providers.deepseek_question_bank import (
    DeepSeekQuestionBankProvider,
    GeneratedChatAnswer,
    GeneratedQuestion,
    GeneratedQuestionEvidence,
    GeneratedQuestions,
    KnowledgePointCandidate,
    KnowledgePointMap,
    QuestionGenerationSection,
)


def test_lists_details_and_isolates_user_learning_state() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        topic = TopicRecord(slug="python", name="Python")
        question = QuestionRecord(
            slug="python-event-loop",
            title="事件循环",
            prompt="解释事件循环",
            difficulty="基础",
            question_type="原理",
            intent="考察异步基础",
            answer_outline=["说明 I/O 等待"],
            common_mistakes=["把异步等同于多线程"],
            published=True,
            created_at=datetime.now(UTC),
            topics=[topic],
        )
        first_user = UserRecord(
            username="first",
            email="first@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        second_user = UserRecord(
            username="second",
            email="second@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add_all([question, first_user, second_user])
        session.commit()
        bank = QuestionBankService(session)

        assert len(bank.list_questions(topic="python", difficulty="基础")) == 1
        public_detail = bank.get_question("python-event-loop")
        assert public_detail.intent == "考察异步基础"
        assert public_detail.editable is False
        saved = bank.update_state(
            user_id=first_user.id,
            question_id=question.id,
            status="learning",
            bookmarked=True,
            note="需要补充自己的项目案例",
        )

        assert saved.bookmarked is True
        assert bank.get_user_state(user_id=first_user.id, question_id=question.id).note
        second_state = bank.get_user_state(user_id=second_user.id, question_id=question.id)
        assert second_state.status == "unseen"
        assert bank.list_review_due(user_id=first_user.id) == []
        bank.update_state(
            user_id=first_user.id,
            question_id=question.id,
            status="review",
            bookmarked=True,
            note="需要重新复习",
        )
        assert [item.id for item in bank.list_review_due(user_id=first_user.id)] == [question.id]


def test_private_question_is_only_visible_and_editable_by_owner() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = UserRecord(
            username="owner",
            email="owner@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        stranger = UserRecord(
            username="stranger",
            email="stranger@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add_all([owner, stranger])
        session.flush()
        session.add(
            QuestionRecord(
                slug="private-question",
                title="个人题目",
                prompt="仅本人可见",
                difficulty="基础",
                question_type="资料题",
                intent="测试权限",
                answer_outline=[],
                common_mistakes=[],
                published=False,
                owner_user_id=owner.id,
                content_markdown="# 私人内容",
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
        bank = QuestionBankService(session)

        assert bank.get_question("private-question", user_id=owner.id).editable is True
        for user_id in (None, stranger.id):
            try:
                bank.get_question("private-question", user_id=user_id)
            except LookupError:
                pass
            else:
                raise AssertionError("非所有者不应读取个人题目")


def test_question_state_updates_spaced_review_schedule() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = UserRecord(
            username="review-user",
            email="review-user@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        question = QuestionRecord(
            slug="review-schedule-question",
            title="复习调度",
            prompt="测试复习调度",
            difficulty="基础",
            question_type="原理",
            intent="测试复习调度",
            answer_outline=[],
            common_mistakes=[],
            published=True,
            created_at=datetime.now(UTC),
        )
        session.add_all([user, question])
        session.commit()
        bank = QuestionBankService(session)

        first = bank.update_state(
            user_id=user.id,
            question_id=question.id,
            status="mastered",
            bookmarked=False,
            note="",
        )
        second = bank.update_state(
            user_id=user.id,
            question_id=question.id,
            status="mastered",
            bookmarked=False,
            note="",
        )

        assert first.review_interval_days == 3
        assert first.review_due_at is not None
        assert first.review_streak == 1
        assert second.review_interval_days == 6
        assert second.review_streak == 2


def test_chat_history_is_restored_and_conversation_is_owner_scoped() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = UserRecord(
            username="chat-owner",
            email="chat-owner@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        stranger = UserRecord(
            username="chat-stranger",
            email="chat-stranger@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        question = QuestionRecord(
            slug="chat-question",
            title="连续问答",
            prompt="解释上下文",
            difficulty="进阶",
            question_type="原理",
            intent="验证连续问答",
            answer_outline=[],
            common_mistakes=[],
            published=True,
            created_at=datetime.now(UTC),
        )
        session.add_all([owner, stranger, question])
        session.flush()
        conversation = QuestionConversationRecord(
            user_id=owner.id,
            question_id=question.id,
            created_at=datetime.now(UTC),
        )
        session.add(conversation)
        session.flush()
        message_time = datetime.now(UTC)
        session.add_all(
            [
                QuestionMessageRecord(
                    id=uuid4(),
                    conversation_id=conversation.id,
                    role="user",
                    content="第一轮问题",
                    citations=[],
                    created_at=message_time,
                ),
                QuestionMessageRecord(
                    id=uuid4(),
                    conversation_id=conversation.id,
                    role="assistant",
                    content="第一轮回答 [1]",
                    citations=[{"index": 1, "title": "题目资料", "quote": "证据"}],
                    created_at=message_time + timedelta(microseconds=1),
                ),
            ]
        )
        session.commit()
        workflow = QuestionWorkflowService(session)

        history = workflow.get_chat_history(user_id=owner.id, question_id=question.id)

        assert history is not None
        assert history.conversation_id == conversation.id
        assert [item.role for item in history.messages] == ["user", "assistant"]
        assert history.messages[1].citations[0].quote == "证据"
        with pytest.raises(LookupError, match="找不到这段题库对话"):
            workflow._owned_conversation(
                user_id=stranger.id,
                question_id=question.id,
                conversation_id=conversation.id,
            )


@pytest.mark.asyncio
async def test_question_chat_prompt_separates_history_from_current_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = DeepSeekQuestionBankProvider(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
    )
    captured = ""

    async def fake_chat(prompt: str) -> str:
        nonlocal captured
        captured = prompt
        return '{"answer_markdown":"结论 [1]","citation_indexes":[1]}'

    monkeypatch.setattr(provider, "_chat", fake_chat)

    result = await provider.answer(
        question="那它的边界条件呢？",
        evidence=["当前证据说明边界条件是连接超时。"],
        history=[
            {"role": "user", "content": "上一轮问题"},
            {"role": "assistant", "content": "上一轮模型回答"},
        ],
    )

    assert result.citation_indexes == [1]
    assert "<历史对话数据>" in captured
    assert "上一轮模型回答" in captured
    assert "不能作为技术事实或引用来源" in captured
    assert "[1] 当前证据说明边界条件是连接超时" in captured


@pytest.mark.asyncio
async def test_question_chat_retrieval_is_scoped_to_selected_question() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = UserRecord(
            username="rag-chat-owner",
            email="rag-chat-owner@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        question = QuestionRecord(
            slug="rag-scoped-question",
            title="RAG 隔离",
            prompt="为什么检索必须隔离？",
            difficulty="进阶",
            question_type="架构",
            intent="验证检索权限",
            answer_outline=[],
            common_mistakes=[],
            published=True,
            content_markdown="检索必须按用户和资料来源隔离。",
            created_at=datetime.now(UTC),
        )
        session.add_all([user, question])
        session.commit()

        class FakeSearch:
            source_ids: list[UUID] = []

            async def search(self, **kwargs: object) -> list[RetrievedEvidence]:
                self.source_ids = list(kwargs["source_ids"])  # type: ignore[arg-type]
                return [
                    RetrievedEvidence(
                        chunk_id=uuid4(),
                        document_id=uuid4(),
                        corpus_type="knowledge",
                        source_type="question",
                        title="RAG 隔离",
                        content="检索必须按用户和资料来源隔离。",
                        heading_path=[],
                        page_start=None,
                        page_end=None,
                        score=0.8,
                        matched_by=["dense", "lexical"],
                    )
                ]

        class FakeDeepSeek:
            async def answer(self, **kwargs: object) -> GeneratedChatAnswer:
                return GeneratedChatAnswer(
                    answer_markdown="需要同时做用户和来源过滤。[1]",
                    citation_indexes=[1],
                )

        search = FakeSearch()
        workflow = QuestionWorkflowService(
            session,
            deepseek=FakeDeepSeek(),  # type: ignore[arg-type]
            rag_search=search,  # type: ignore[arg-type]
        )
        answer = await workflow.chat(
            user_id=user.id,
            question_id=question.id,
            message="如何避免串数据？",
        )

        assert search.source_ids == [question.id]
        assert answer.citations[0].quote == "检索必须按用户和资料来源隔离。"


def test_generated_questions_keep_only_exact_source_evidence() -> None:
    sections = [
        QuestionGenerationSection(
            key="section-0",
            heading_path=["项目复盘"],
            content="我负责检索评测，并将召回率从 70% 提升到 86%。",
        )
    ]
    base = {
        "prompt": "你如何证明这项改进有效？",
        "difficulty": "进阶",
        "question_type": "项目",
        "framework": "star",
        "intent": "考察结果表达",
        "answer_outline": ["说明职责", "量化结果"],
        "common_mistakes": ["缺少证据"],
        "topics": ["检索"],
        "content_markdown": "# 回答框架",
    }
    generated = GeneratedQuestions(
        questions=[
            GeneratedQuestion(
                title="有效证据",
                evidence=[
                    GeneratedQuestionEvidence(
                        section_key="section-0", quote="召回率从 70% 提升到 86%"
                    )
                ],
                **base,
            ),
            GeneratedQuestion(
                title="编造证据",
                evidence=[
                    GeneratedQuestionEvidence(section_key="section-0", quote="成本降低了 50%")
                ],
                **base,
            ),
        ]
    )

    result = DeepSeekQuestionBankProvider._validate_evidence(generated, sections)

    assert [item.title for item in result.questions] == ["有效证据"]
    assert "编造证据" in result.warnings[0]


def test_evidence_matching_tolerates_pdf_layout_but_returns_source_text() -> None:
    source = "模型调用失败时，先做指数退避；\n超过阈值后进入降级流程。"

    matched = DeepSeekQuestionBankProvider._match_quote(
        source, "模型调用失败时,先做指数退避; 超过阈值后进入降级流程。"
    )

    assert matched == source
    assert DeepSeekQuestionBankProvider._match_quote(source, "应永久关闭模型调用") is None


@pytest.mark.asyncio
async def test_generation_repairs_non_exact_evidence_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = DeepSeekQuestionBankProvider(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
    )
    section = QuestionGenerationSection(
        key="section-0",
        content="系统使用令牌桶限制突发流量。",
    )
    base = {
        "title": "限流策略",
        "prompt": "如何限制突发流量？",
        "difficulty": "进阶",
        "question_type": "取舍",
        "framework": "prep",
        "intent": "考察限流设计",
        "answer_outline": ["说明目标", "解释方案"],
        "common_mistakes": ["忽略突发流量"],
        "topics": ["限流"],
        "content_markdown": "旧的错误引用",
    }
    responses = iter(
        [
            json.dumps(
                {
                    "questions": [
                        {
                            **base,
                            "evidence": [
                                {
                                    "section_key": "section-0",
                                    "quote": "令牌桶能够限制流量",
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "questions": [
                        {
                            **base,
                            "content_markdown": "",
                            "evidence": [
                                {
                                    "section_key": "section-0",
                                    "quote": "使用令牌桶限制突发流量",
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
        ]
    )

    async def fake_chat(prompt: str) -> str:
        del prompt
        return next(responses)

    monkeypatch.setattr(provider, "_chat", fake_chat)

    result = await provider.generate_questions([section], desired_questions=1)

    assert result.questions[0].evidence[0].quote == "使用令牌桶限制突发流量"
    assert "使用令牌桶限制突发流量" not in result.questions[0].content_markdown
    assert "### 一句话回答" in result.questions[0].content_markdown
    assert "旧的错误引用" not in result.questions[0].content_markdown


def test_generated_questions_accept_fenced_json_and_keep_valid_items() -> None:
    valid = {
        "title": "解释限流策略",
        "prompt": "如何选择限流算法？",
        "difficulty": "进阶",
        "question_type": "取舍",
        "framework": "prep",
        "intent": "考察方案权衡",
        "answer_outline": ["说明目标", "比较方案"],
        "common_mistakes": ["忽略突发流量"],
        "topics": ["限流"],
        "evidence": [{"section_key": "section-0", "quote": "使用令牌桶限制流量"}],
    }
    payload = (
        "```json\n"
        f'{{"questions":[{json.dumps(valid, ensure_ascii=False)},'
        '{"title":"坏题"}]}\n```'
    )

    generated, errors = DeepSeekQuestionBankProvider._parse_generated(payload)

    assert generated is not None
    assert [item.title for item in generated.questions] == ["解释限流策略"]
    assert any("无效题目已跳过" in warning for warning in generated.warnings)
    assert any("questions[1]" in error for error in errors)


def test_generated_question_builds_learning_content_when_model_omits_it() -> None:
    question = GeneratedQuestion(
        title="解释限流策略",
        prompt="如何选择限流算法？",
        difficulty="进阶",
        question_type="取舍",
        framework="prep",
        intent="考察方案权衡",
        answer_outline=["说明目标", "比较方案"],
        common_mistakes=["忽略突发流量"],
        topics=["限流"],
        evidence=[GeneratedQuestionEvidence(section_key="section-0", quote="使用令牌桶限制流量")],
    )

    normalized = DeepSeekQuestionBankProvider._with_content(question)

    assert "### 一句话回答" in normalized.content_markdown
    assert "使用令牌桶限制流量" not in normalized.content_markdown


@pytest.mark.asyncio
async def test_imported_document_deduplicates_versions_and_preserves_coverage() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = UserRecord(
            username="document-owner",
            email="document-owner@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        stranger = UserRecord(
            username="document-stranger",
            email="document-stranger@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add_all([owner, stranger])
        session.commit()

        class FakeProvider:
            model_name = "fake-question-model"
            prompt_version = "question-test-v1"

            async def extract_knowledge_points(
                self, sections: list[QuestionGenerationSection]
            ) -> KnowledgePointMap:
                return KnowledgePointMap(
                    knowledge_points=[
                        KnowledgePointCandidate(
                            stable_key=f"project-retrieval-{index}",
                            title="检索评测",
                            knowledge_type="项目",
                            interview_claim="我用召回率和发布门禁验证检索效果。",
                            section_keys=[section.key],
                        )
                        for index, section in enumerate(sections)
                    ]
                )

            async def generate_questions(
                self,
                sections: list[QuestionGenerationSection],
                *,
                desired_questions: int,
                knowledge_points: list[KnowledgePointCandidate] | None = None,
            ) -> GeneratedQuestions:
                del desired_questions
                return GeneratedQuestions(
                    questions=[
                        GeneratedQuestion(
                            title=f"片段 {section.key}",
                            knowledge_point_key=(knowledge_points or [])[0].stable_key,
                            prompt="这段经历如何体现个人贡献？",
                            difficulty="进阶",
                            question_type="项目",
                            framework="star",
                            intent="考察结构化项目表达",
                            answer_outline=["说明职责", "量化结果"],
                            common_mistakes=["只讲团队"],
                            topics=["项目复盘"],
                            evidence=[
                                GeneratedQuestionEvidence(
                                    section_key=section.key,
                                    quote="召回率从 70% 提升到 86%",
                                )
                            ],
                            content_markdown="# 项目复盘",
                        )
                        for section in sections
                    ]
                )

        class FakeIndexing:
            source_ids: list[UUID] = []

            async def index(self, document: object) -> None:
                self.source_ids.append(document.source_id)  # type: ignore[attr-defined]

        text = "我独立负责检索评测，将召回率从 70% 提升到 86%，并接入发布门禁。"
        workflow = QuestionWorkflowService(
            session,
            deepseek=FakeProvider(),  # type: ignore[arg-type]
            rag_indexing=FakeIndexing(),  # type: ignore[arg-type]
        )
        first = await workflow.import_document(
            user_id=owner.id,
            filename="项目复盘.md",
            media_type="text/markdown",
            text=text,
        )
        duplicate = await workflow.import_document(
            user_id=owner.id,
            filename="副本.md",
            media_type="text/markdown",
            text=text,
        )
        assert first.document.coverage_ratio == 1
        assert first.document.knowledge_point_count == 1
        assert first.questions[0].framework == "star"
        assert first.questions[0].evidence[0].quote in text
        assert duplicate.document.id == first.document.id
        assert "相同内容已经导入" in duplicate.warnings[0]
        with pytest.raises(ValueError, match="知识点已经全部生成"):
            await workflow.regenerate_document(
                user_id=owner.id,
                document_id=first.document.id,
            )
        assert len(workflow.list_documents(user_id=owner.id)) == 1
        with pytest.raises(LookupError, match="找不到这份题库资料"):
            await workflow.regenerate_document(
                user_id=stranger.id,
                document_id=first.document.id,
            )
        workflow.delete_document(user_id=owner.id, document_id=first.document.id)
        assert len(workflow.list_documents(user_id=owner.id)) == 0


@pytest.mark.asyncio
async def test_import_commits_questions_progressively_per_batch() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = UserRecord(
            username="progressive-owner",
            email="progressive-owner@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add(owner)
        session.commit()

        progress_events: list[tuple[str, int]] = []
        visible_counts: list[int] = []

        class FakeProvider:
            model_name = "fake-question-model"
            prompt_version = "question-test-v1"
            calls = 0

            async def extract_knowledge_points(
                self, sections: list[QuestionGenerationSection]
            ) -> KnowledgePointMap:
                return KnowledgePointMap(
                    knowledge_points=[
                        KnowledgePointCandidate(
                            stable_key=f"point-{section.key}",
                            title=f"知识点 {section.key}",
                            knowledge_type="概念",
                            interview_claim=f"{section.key} 的核心判断",
                            section_keys=[section.key],
                        )
                        for section in sections
                    ]
                )

            async def generate_questions(
                self,
                sections: list[QuestionGenerationSection],
                *,
                desired_questions: int,
                knowledge_points: list[KnowledgePointCandidate] | None = None,
            ) -> GeneratedQuestions:
                del desired_questions
                self.calls += 1
                points = knowledge_points or []
                return GeneratedQuestions(
                    questions=[
                        GeneratedQuestion(
                            title=f"题 {point.stable_key}",
                            knowledge_point_key=point.stable_key,
                            prompt=f"请解释 {point.title}",
                            difficulty="基础",
                            question_type="原理",
                            framework="technical",
                            intent="考察理解",
                            answer_outline=["定义", "例子"],
                            common_mistakes=["只会背定义"],
                            topics=["渐进生成"],
                            evidence=[
                                GeneratedQuestionEvidence(
                                    section_key=point.section_keys[0],
                                    quote=f"证据来自 {point.section_keys[0]}",
                                )
                            ],
                            content_markdown=f"# {point.title}",
                        )
                        for point in points
                    ]
                )

        class FakeIndexing:
            async def index(self, document: object) -> None:
                del document

        # Multiple short paragraphs force multiple generation batches (4 knowledge points/batch).
        paragraphs = [
            f"第{index}段。这是可独立抽题的技术说明，覆盖检索、缓存、限流与发布门禁。"
            for index in range(1, 10)
        ]
        text = "\n\n".join(paragraphs)
        workflow = QuestionWorkflowService(
            session,
            deepseek=FakeProvider(),  # type: ignore[arg-type]
            rag_indexing=FakeIndexing(),  # type: ignore[arg-type]
        )

        def progress(stage: str, value: int, resource_id: UUID | None) -> None:
            del resource_id
            progress_events.append((stage, value))
            count = int(
                session.scalar(
                    select(func.count())
                    .select_from(QuestionRecord)
                    .where(QuestionRecord.owner_user_id == owner.id)
                )
                or 0
            )
            visible_counts.append(count)

        result = await workflow.import_document(
            user_id=owner.id,
            filename="渐进生成.md",
            media_type="text/markdown",
            text=text,
            progress=progress,
            question_limit=12,
        )

        assert result.document.status == "ready"
        assert len(result.questions) >= 1
        assert any(count > 0 for count in visible_counts[:-1]), (
            "questions should become readable before final completion"
        )
        assert any("已生成" in stage for stage, _ in progress_events)
        final_count = int(
            session.scalar(
                select(func.count())
                .select_from(QuestionRecord)
                .where(QuestionRecord.owner_user_id == owner.id)
            )
            or 0
        )
        assert final_count == len(result.questions)


def test_question_plan_uses_knowledge_points_and_respects_type_mix() -> None:
    types = ["概念"] * 20 + ["机制"] * 8 + ["对比"] * 5 + ["场景"] * 5
    points = [
        KnowledgePointCandidate(
            stable_key=f"knowledge-point-{index}",
            title=f"知识点 {index}",
            knowledge_type=knowledge_type,  # type: ignore[arg-type]
            interview_claim=f"这是可以直接表达的结论 {index}",
            section_keys=[f"section-{index}"],
        )
        for index, knowledge_type in enumerate(types)
    ]

    plan = QuestionWorkflowService._question_plan(points, min(30, int(len(points) * 1.2)))

    assert sum(count for _, count in plan) == 30
    selected_types = {point.knowledge_type for point, _ in plan}
    assert selected_types == {"概念", "机制", "对比", "场景"}


def test_question_plan_keeps_explicit_document_anchors_first() -> None:
    points = [
        KnowledgePointCandidate(
            stable_key=f"document-anchor-{index}",
            title=f"明确问题 {index}",
            knowledge_type="场景",
            interview_claim=f"回答明确问题 {index}",
            section_keys=[f"section-{index}"],
        )
        for index in range(6)
    ] + [
        KnowledgePointCandidate(
            stable_key=f"concept-point-{index}",
            title=f"概念 {index}",
            knowledge_type="概念",
            interview_claim=f"解释概念 {index}",
            section_keys=[f"section-{index + 6}"],
        )
        for index in range(10)
    ]

    plan = QuestionWorkflowService._question_plan(
        points,
        8,
        priority_keys={point.stable_key for point in points[:6]},
    )

    assert [point.stable_key for point, _ in plan[:6]] == [point.stable_key for point in points[:6]]
    assert sum(count for _, count in plan) == 8


@pytest.mark.asyncio
async def test_knowledge_point_merge_batches_large_candidate_sets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = DeepSeekQuestionBankProvider(
        api_key="test-key",
        base_url="https://example.invalid",
        model="test-model",
    )
    calls = 0

    async def fake_chat(prompt: str) -> str:
        nonlocal calls
        calls += 1
        del prompt
        return json.dumps(
            {
                "knowledge_points": [
                    {
                        "stable_key": f"merged-point-{calls}",
                        "title": f"合并知识点 {calls}",
                        "knowledge_type": "概念",
                        "interview_claim": "这是可以直接表达的核心判断。",
                        "section_keys": ["section-0"],
                    }
                ]
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(provider, "_chat", fake_chat)
    candidates = [
        KnowledgePointCandidate(
            stable_key=f"candidate-point-{index}",
            title=f"候选知识点 {index}",
            knowledge_type="概念",
            interview_claim="这是候选知识点的核心判断。",
            section_keys=["section-0"],
        )
        for index in range(25)
    ]

    result = await provider.merge_knowledge_points(candidates)

    assert calls == 2
    assert len(result.knowledge_points) == 2


def test_knowledge_point_dedupe_keeps_first_verified_candidate() -> None:
    first = KnowledgePointCandidate(
        stable_key="first-point",
        title="同一个知识点",
        knowledge_type="概念",
        interview_claim="先出现的候选应被保留。",
        section_keys=["section-0"],
    )
    duplicate = first.model_copy(
        update={"stable_key": "duplicate-point", "interview_claim": "重复候选。"}
    )

    result = DeepSeekQuestionBankProvider._dedupe_points([first, duplicate])

    assert [item.stable_key for item in result] == ["first-point"]

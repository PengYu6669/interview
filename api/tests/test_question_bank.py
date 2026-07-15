from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
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

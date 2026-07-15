from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.retrieval.indexing import RagIndexingService
from interview_copilot.application.retrieval.search import (
    RagSearchService,
    fuse_retrieval_results,
)
from interview_copilot.domain.retrieval import (
    RagChunkInput,
    RagDocumentInput,
    RetrievalCandidate,
)
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.rag import RagChunkRecord, RagDocumentRecord
from interview_copilot.infrastructure.rag_store import SqlAlchemyRagStore


class FakeEmbedding:
    async def embed(self, text: str) -> list[float]:
        return [float(len(text))]


class CapturingStore:
    def __init__(self) -> None:
        self.document_id = uuid4()
        self.call: dict | None = None

    def replace_document(self, **kwargs: object) -> UUID:
        self.call = kwargs
        return self.document_id


@pytest.mark.asyncio
async def test_indexing_normalizes_chunks_and_persists_source_metadata() -> None:
    store = CapturingStore()
    service = RagIndexingService(store, FakeEmbedding())
    source_id = uuid4()
    user_id = uuid4()

    result = await service.index(
        RagDocumentInput(
            owner_user_id=user_id,
            corpus_type="knowledge",
            source_type="question",
            source_id=source_id,
            title="RAG 检索",
            text="# 检索\r\n\r\n向量召回和关键词召回。",
            metadata={"question_id": str(source_id)},
        )
    )

    assert result.id == store.document_id
    assert result.chunk_count == 1
    assert store.call is not None
    chunks = store.call["chunks"]
    assert len(chunks) == 1  # type: ignore[arg-type]
    assert chunks[0].heading_path == ["检索"]  # type: ignore[index,union-attr]
    assert len(store.call["content_hash"]) == 64  # type: ignore[arg-type]
    assert isinstance(store.call["indexed_at"], datetime)


def _candidate(
    chunk_id: UUID,
    *,
    dense: float | None = None,
    lexical: float | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        document_id=uuid4(),
        corpus_type="knowledge",
        source_type="question",
        title="测试资料",
        content="证据内容",
        dense_similarity=dense,
        lexical_score=lexical,
    )


def test_rrf_prefers_cross_channel_hits_and_filters_irrelevant_results() -> None:
    shared = uuid4()
    dense_only = uuid4()
    irrelevant = uuid4()
    results = fuse_retrieval_results(
        [
            _candidate(dense_only, dense=0.8),
            _candidate(shared, dense=0.7),
            _candidate(irrelevant, dense=0.1),
        ],
        [_candidate(shared, lexical=0.5)],
        limit=5,
    )

    assert [item.chunk_id for item in results] == [shared, dense_only]
    assert results[0].matched_by == ["dense", "lexical"]
    assert irrelevant not in [item.chunk_id for item in results]


def test_dense_only_results_below_answerability_threshold_are_rejected() -> None:
    weak = uuid4()
    sufficient = uuid4()

    results = fuse_retrieval_results(
        [
            _candidate(weak, dense=0.34),
            _candidate(sufficient, dense=0.36),
        ],
        [],
        limit=5,
    )

    assert [item.chunk_id for item in results] == [sufficient]


@pytest.mark.asyncio
async def test_search_requires_corpus_and_uses_both_retrieval_channels() -> None:
    class Repository:
        dense_called = False
        lexical_called = False

        def dense_search(self, **kwargs: object) -> list[RetrievalCandidate]:
            self.dense_called = True
            return []

        def lexical_search(self, **kwargs: object) -> list[RetrievalCandidate]:
            self.lexical_called = True
            return []

    repository = Repository()
    service = RagSearchService(repository, FakeEmbedding())
    with pytest.raises(ValueError, match="至少选择"):
        await service.search(user_id=uuid4(), query="RAG", corpus_types=[])

    assert await service.search(
        user_id=uuid4(), query="  RAG   检索 ", corpus_types=["knowledge"]
    ) == []
    assert repository.dense_called is True
    assert repository.lexical_called is True


def test_sqlalchemy_store_populates_required_fields_before_flush() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        user = UserRecord(
            username="rag-store-owner",
            email="rag-store-owner@example.com",
            password_hash="hash",
            created_at=datetime.now().astimezone(),
        )
        session.add(user)
        session.flush()
        source_id = uuid4()
        document_id = SqlAlchemyRagStore(session).replace_document(
            document=RagDocumentInput(
                owner_user_id=user.id,
                corpus_type="knowledge",
                source_type="question",
                source_id=source_id,
                title="混合检索",
                text="检索内容",
            ),
            normalized_text="检索内容",
            content_hash="a" * 64,
            warnings=[],
            chunks=[
                RagChunkInput(
                    content="检索内容",
                    heading_path=[],
                    token_count=4,
                    chunk_index=0,
                    content_hash="b" * 64,
                    embedding=[1.0],
                )
            ],
            indexed_at=datetime.now().astimezone(),
        )

        stored = session.get(RagDocumentRecord, document_id)
        chunks = session.query(RagChunkRecord).filter_by(document_id=document_id).all()
        assert stored is not None
        assert stored.corpus_type == "knowledge"
        assert stored.title == "混合检索"
        assert len(chunks) == 1

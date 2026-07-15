from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from interview_copilot.domain.retrieval import (
    CorpusType,
    RetrievalCandidate,
    RetrievedEvidence,
)

from .indexing import TextEmbeddingProvider


class RagSearchRepository(Protocol):
    def dense_search(
        self,
        *,
        user_id: UUID,
        query_vector: list[float],
        corpus_types: Sequence[CorpusType],
        source_types: Sequence[str],
        source_ids: Sequence[UUID],
        limit: int,
    ) -> list[RetrievalCandidate]: ...

    def lexical_search(
        self,
        *,
        user_id: UUID,
        query: str,
        corpus_types: Sequence[CorpusType],
        source_types: Sequence[str],
        source_ids: Sequence[UUID],
        limit: int,
    ) -> list[RetrievalCandidate]: ...


class RagSearchService:
    def __init__(
        self,
        repository: RagSearchRepository,
        embedding: TextEmbeddingProvider,
        *,
        rrf_k: int = 60,
        min_dense_similarity: float = 0.35,
        min_lexical_score: float = 0.03,
    ) -> None:
        self._repository = repository
        self._embedding = embedding
        self._rrf_k = rrf_k
        self._min_dense_similarity = min_dense_similarity
        self._min_lexical_score = min_lexical_score

    async def search(
        self,
        *,
        user_id: UUID,
        query: str,
        corpus_types: Sequence[CorpusType],
        source_types: Sequence[str] = (),
        source_ids: Sequence[UUID] = (),
        limit: int = 8,
    ) -> list[RetrievedEvidence]:
        clean_query = " ".join(query.split())
        if not clean_query:
            raise ValueError("检索问题不能为空")
        if not corpus_types:
            raise ValueError("至少选择一种检索语料")
        if not 1 <= limit <= 20:
            raise ValueError("检索结果数量必须为 1 至 20")

        query_vector = await self._embedding.embed(clean_query)
        candidate_limit = min(60, max(limit * 4, 20))
        dense = self._repository.dense_search(
            user_id=user_id,
            query_vector=query_vector,
            corpus_types=corpus_types,
            source_types=source_types,
            source_ids=source_ids,
            limit=candidate_limit,
        )
        lexical = self._repository.lexical_search(
            user_id=user_id,
            query=clean_query,
            corpus_types=corpus_types,
            source_types=source_types,
            source_ids=source_ids,
            limit=candidate_limit,
        )
        return fuse_retrieval_results(
            dense,
            lexical,
            limit=limit,
            rrf_k=self._rrf_k,
            min_dense_similarity=self._min_dense_similarity,
            min_lexical_score=self._min_lexical_score,
        )


def fuse_retrieval_results(
    dense: Sequence[RetrievalCandidate],
    lexical: Sequence[RetrievalCandidate],
    *,
    limit: int,
    rrf_k: int = 60,
    min_dense_similarity: float = 0.35,
    min_lexical_score: float = 0.03,
) -> list[RetrievedEvidence]:
    candidates: dict[UUID, RetrievalCandidate] = {}
    scores: dict[UUID, float] = {}
    matched_by: dict[UUID, list[str]] = {}

    for method, items in (("dense", dense), ("lexical", lexical)):
        for rank, item in enumerate(items, 1):
            if method == "dense" and (item.dense_similarity or 0) < min_dense_similarity:
                continue
            if method == "lexical" and (item.lexical_score or 0) < min_lexical_score:
                continue
            candidates[item.chunk_id] = item
            scores[item.chunk_id] = scores.get(item.chunk_id, 0) + 1 / (rrf_k + rank)
            matched_by.setdefault(item.chunk_id, []).append(method)

    maximum_score = 2 / (rrf_k + 1)
    ranked = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)[:limit]
    return [
        RetrievedEvidence(
            chunk_id=candidates[chunk_id].chunk_id,
            document_id=candidates[chunk_id].document_id,
            corpus_type=candidates[chunk_id].corpus_type,
            source_type=candidates[chunk_id].source_type,
            title=candidates[chunk_id].title,
            content=candidates[chunk_id].content,
            heading_path=candidates[chunk_id].heading_path,
            page_start=candidates[chunk_id].page_start,
            page_end=candidates[chunk_id].page_end,
            source_metadata=candidates[chunk_id].source_metadata,
            score=min(1.0, scores[chunk_id] / maximum_score),
            matched_by=matched_by[chunk_id],  # type: ignore[arg-type]
        )
        for chunk_id in ranked
    ]

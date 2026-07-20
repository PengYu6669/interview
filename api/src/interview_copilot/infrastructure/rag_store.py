from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.orm import Session

from interview_copilot.domain.retrieval import (
    CorpusType,
    RagChunkInput,
    RagDocumentInput,
    RetrievalCandidate,
)

from .rag import RagChunkRecord, RagDocumentRecord


class SqlAlchemyRagStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_document(
        self,
        *,
        document: RagDocumentInput,
        normalized_text: str,
        content_hash: str,
        warnings: Sequence[str],
        chunks: Sequence[RagChunkInput],
        indexed_at: datetime,
    ) -> UUID:
        filters = [
            RagDocumentRecord.owner_user_id == document.owner_user_id,
            RagDocumentRecord.source_type == document.source_type,
        ]
        filters.append(
            RagDocumentRecord.source_id.is_(None)
            if document.source_id is None
            else RagDocumentRecord.source_id == document.source_id
        )
        record = self._session.scalar(select(RagDocumentRecord).where(*filters))
        if record is None:
            record = RagDocumentRecord(
                owner_user_id=document.owner_user_id,
                source_type=document.source_type,
                source_id=document.source_id,
                created_at=indexed_at,
            )
            self._session.add(record)
        else:
            self._session.execute(
                delete(RagChunkRecord).where(RagChunkRecord.document_id == record.id)
            )
        record.corpus_type = document.corpus_type
        record.visibility = document.visibility
        record.title = document.title
        record.normalized_text = normalized_text
        record.content_hash = content_hash
        record.quality_warnings = list(warnings)
        record.source_metadata = document.metadata
        record.updated_at = indexed_at
        self._session.flush()
        self._session.add_all(
            RagChunkRecord(
                document_id=record.id,
                corpus_type=document.corpus_type,
                content=chunk.content,
                heading_path=chunk.heading_path,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                token_count=chunk.token_count,
                chunk_index=chunk.chunk_index,
                content_hash=chunk.content_hash,
                embedding=chunk.embedding,
                created_at=indexed_at,
            )
            for chunk in chunks
        )
        self._session.flush()
        return record.id

    def set_question_visibility(
        self, *, question_id: UUID, owner_user_id: UUID | None, visibility: str
    ) -> None:
        record = self._session.scalar(
            select(RagDocumentRecord).where(
                RagDocumentRecord.source_type == "question",
                RagDocumentRecord.source_id == question_id,
            )
        )
        if not record:
            return
        record.owner_user_id = owner_user_id
        record.visibility = visibility
        self._session.flush()

    def delete_question(self, *, question_id: UUID) -> None:
        record = self._session.scalar(
            select(RagDocumentRecord).where(
                RagDocumentRecord.source_type == "question",
                RagDocumentRecord.source_id == question_id,
            )
        )
        if record:
            self._session.delete(record)
            self._session.flush()


class PostgresRagSearchRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def dense_search(
        self,
        *,
        user_id: UUID,
        query_vector: list[float],
        corpus_types: Sequence[CorpusType],
        source_types: Sequence[str],
        source_ids: Sequence[UUID],
        limit: int,
    ) -> list[RetrievalCandidate]:
        distance = RagChunkRecord.embedding.cosine_distance(query_vector)
        statement = (
            select(RagChunkRecord, RagDocumentRecord, distance.label("distance"))
            .join(RagDocumentRecord, RagDocumentRecord.id == RagChunkRecord.document_id)
            .where(
                RagChunkRecord.embedding.is_not(None),
                RagDocumentRecord.corpus_type.in_(corpus_types),
                self._visible_to(user_id),
            )
            .order_by(distance)
            .limit(limit)
        )
        if source_types:
            statement = statement.where(RagDocumentRecord.source_type.in_(source_types))
        if source_ids:
            statement = statement.where(RagDocumentRecord.source_id.in_(source_ids))
        rows = self._session.execute(statement).all()
        return [
            self._candidate(chunk, document, dense_similarity=max(0.0, 1 - float(distance)))
            for chunk, document, distance in rows
        ]

    def lexical_search(
        self,
        *,
        user_id: UUID,
        query: str,
        corpus_types: Sequence[CorpusType],
        source_types: Sequence[str],
        source_ids: Sequence[UUID],
        limit: int,
    ) -> list[RetrievalCandidate]:
        ts_query = func.websearch_to_tsquery("simple", query)
        rank = func.ts_rank_cd(func.to_tsvector("simple", RagChunkRecord.content), ts_query)
        trigram = func.similarity(RagChunkRecord.content, query)
        escaped_query = _escape_like(query)
        contains_query = RagChunkRecord.content.ilike(f"%{escaped_query}%", escape="\\")
        exact_substring = case((contains_query, 1.0), else_=0.0)
        lexical_score = func.greatest(rank, trigram, exact_substring).label("lexical_score")
        statement = (
            select(RagChunkRecord, RagDocumentRecord, lexical_score)
            .join(RagDocumentRecord, RagDocumentRecord.id == RagChunkRecord.document_id)
            .where(
                RagDocumentRecord.corpus_type.in_(corpus_types),
                self._visible_to(user_id),
                or_(
                    func.to_tsvector("simple", RagChunkRecord.content).op("@@")(ts_query),
                    RagChunkRecord.content.op("%>")(query),
                    contains_query,
                ),
            )
            .order_by(lexical_score.desc())
            .limit(limit)
        )
        if source_types:
            statement = statement.where(RagDocumentRecord.source_type.in_(source_types))
        if source_ids:
            statement = statement.where(RagDocumentRecord.source_id.in_(source_ids))
        rows = self._session.execute(statement).all()
        return [
            self._candidate(chunk, document, lexical_score=float(score or 0))
            for chunk, document, score in rows
        ]

    @staticmethod
    def _visible_to(user_id: UUID):  # type: ignore[no-untyped-def]
        return or_(
            RagDocumentRecord.owner_user_id == user_id,
            RagDocumentRecord.visibility == "public",
        )

    @staticmethod
    def _candidate(
        chunk: RagChunkRecord,
        document: RagDocumentRecord,
        *,
        dense_similarity: float | None = None,
        lexical_score: float | None = None,
    ) -> RetrievalCandidate:
        return RetrievalCandidate(
            chunk_id=chunk.id,
            document_id=document.id,
            corpus_type=document.corpus_type,  # type: ignore[arg-type]
            source_type=document.source_type,
            title=document.title,
            content=chunk.content,
            heading_path=chunk.heading_path,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            source_metadata=document.source_metadata,
            dense_similarity=dense_similarity,
            lexical_score=lexical_score,
        )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

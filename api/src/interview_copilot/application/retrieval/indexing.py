import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from interview_copilot.domain.retrieval import (
    IndexedRagDocument,
    RagChunkInput,
    RagDocumentInput,
)

from .chunking import split_semantic_chunks
from .normalization import normalize_document_text


class TextEmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class RagDocumentStore(Protocol):
    def replace_document(
        self,
        *,
        document: RagDocumentInput,
        normalized_text: str,
        content_hash: str,
        warnings: Sequence[str],
        chunks: Sequence[RagChunkInput],
        indexed_at: datetime,
    ) -> UUID: ...


class RagIndexingService:
    def __init__(
        self,
        store: RagDocumentStore,
        embedding: TextEmbeddingProvider,
        *,
        embedding_concurrency: int = 3,
    ) -> None:
        if not 1 <= embedding_concurrency <= 8:
            raise ValueError("Embedding 并发数必须为 1 至 8")
        self._store = store
        self._embedding = embedding
        self._embedding_concurrency = embedding_concurrency

    async def index(self, document: RagDocumentInput) -> IndexedRagDocument:
        if document.visibility == "private" and document.owner_user_id is None:
            raise ValueError("私有语料必须关联用户")
        normalized = normalize_document_text(document.text)
        chunks = split_semantic_chunks(normalized.text)
        if not chunks:
            raise ValueError("文档规范化后没有可索引内容")

        semaphore = asyncio.Semaphore(self._embedding_concurrency)

        async def embed(content: str) -> list[float]:
            async with semaphore:
                return await self._embedding.embed(content[:4000])

        vectors = await asyncio.gather(*(embed(chunk.content) for chunk in chunks))
        chunk_inputs = [
            RagChunkInput(
                content=chunk.content,
                heading_path=list(chunk.heading_path),
                token_count=chunk.token_count,
                chunk_index=chunk.index,
                content_hash=chunk.content_hash,
                embedding=vector,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        indexed_at = datetime.now(UTC)
        document_id = self._store.replace_document(
            document=document,
            normalized_text=normalized.text,
            content_hash=sha256(normalized.text.encode("utf-8")).hexdigest(),
            warnings=normalized.warnings,
            chunks=chunk_inputs,
            indexed_at=indexed_at,
        )
        return IndexedRagDocument(
            id=document_id,
            corpus_type=document.corpus_type,
            source_type=document.source_type,
            title=document.title,
            chunk_count=len(chunk_inputs),
            warnings=list(normalized.warnings),
            indexed_at=indexed_at,
        )


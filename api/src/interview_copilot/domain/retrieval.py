from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

CorpusType = Literal["candidate", "job", "knowledge"]
Visibility = Literal["private", "public"]


class RagDocumentInput(BaseModel):
    owner_user_id: UUID | None
    corpus_type: CorpusType
    source_type: str = Field(min_length=1, max_length=40)
    source_id: UUID | None = None
    visibility: Visibility = "private"
    title: str = Field(min_length=1, max_length=250)
    text: str = Field(min_length=1, max_length=200_000)
    metadata: dict = Field(default_factory=dict)


class RagChunkInput(BaseModel):
    content: str
    heading_path: list[str]
    token_count: int = Field(gt=0)
    chunk_index: int = Field(ge=0)
    content_hash: str = Field(min_length=64, max_length=64)
    embedding: list[float]
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)


class IndexedRagDocument(BaseModel):
    id: UUID
    corpus_type: CorpusType
    source_type: str
    title: str
    chunk_count: int
    warnings: list[str]
    indexed_at: datetime


class RetrievalCandidate(BaseModel):
    chunk_id: UUID
    document_id: UUID
    corpus_type: CorpusType
    source_type: str
    title: str
    content: str
    heading_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    source_metadata: dict = Field(default_factory=dict)
    dense_similarity: float | None = None
    lexical_score: float | None = None


class RetrievedEvidence(BaseModel):
    chunk_id: UUID
    document_id: UUID
    corpus_type: CorpusType
    source_type: str
    title: str
    content: str
    heading_path: list[str]
    page_start: int | None
    page_end: int | None
    source_metadata: dict = Field(default_factory=dict)
    score: float = Field(ge=0, le=1)
    matched_by: list[Literal["dense", "lexical"]]

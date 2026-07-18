from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TopicData(BaseModel):
    id: UUID
    slug: str
    name: str


class SourceData(BaseModel):
    title: str
    url: str
    publisher: str


class QuestionEvidenceData(BaseModel):
    section_key: str
    heading_path: list[str]
    quote: str


class QuestionSummary(BaseModel):
    id: UUID
    slug: str
    title: str
    prompt: str
    difficulty: str
    question_type: str
    topics: list[TopicData]
    framework: str = "technical"
    source_document_id: UUID | None = None
    source_document_name: str | None = None
    source_document_version: int | None = None


class QuestionDetail(QuestionSummary):
    intent: str
    answer_outline: list[str]
    common_mistakes: list[str]
    sources: list[SourceData]
    content_markdown: str = ""
    editable: bool = False
    evidence: list[QuestionEvidenceData] = Field(default_factory=list)


class QuestionDocumentSummary(BaseModel):
    id: UUID
    filename: str
    media_type: str
    version: int
    status: str
    warnings: list[str]
    coverage_ratio: float = Field(ge=0, le=1)
    section_count: int = Field(ge=0)
    covered_section_count: int = Field(ge=0)
    question_count: int = Field(ge=0)
    knowledge_point_count: int = Field(default=0, ge=0)
    covered_knowledge_point_count: int = Field(default=0, ge=0)
    suggested_question_count: int = Field(default=0, ge=0, le=100)
    requested_question_limit: int = Field(default=30, ge=10, le=100)
    created_at: datetime
    updated_at: datetime


class QuestionImportResult(BaseModel):
    document: QuestionDocumentSummary
    questions: list[QuestionDetail]
    warnings: list[str] = Field(default_factory=list)


class QuestionSetSummary(BaseModel):
    id: UUID
    name: str
    kind: str
    status: str
    target_count: int = Field(ge=0, le=100)
    question_count: int = Field(ge=0)
    document_id: UUID | None = None
    document_name: str | None = None
    knowledge_point_count: int = Field(default=0, ge=0)
    covered_knowledge_point_count: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime


class QuestionSetDetail(QuestionSetSummary):
    questions: list[QuestionSummary]


class CitationData(BaseModel):
    index: int
    title: str
    url: str | None = None
    quote: str


class QuestionChatAnswer(BaseModel):
    answer_markdown: str
    citations: list[CitationData]
    conversation_id: UUID


class QuestionChatMessageData(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str
    citations: list[CitationData] = Field(default_factory=list)
    created_at: datetime


class QuestionChatHistory(BaseModel):
    conversation_id: UUID
    messages: list[QuestionChatMessageData]


class UserQuestionState(BaseModel):
    status: str = "unseen"
    bookmarked: bool = False
    note: str = ""
    review_interval_days: int = Field(default=0, ge=0, le=365)
    review_streak: int = Field(default=0, ge=0, le=10_000)
    last_reviewed_at: datetime | None = None
    review_due_at: datetime | None = None

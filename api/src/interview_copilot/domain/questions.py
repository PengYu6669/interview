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


class QuestionSummary(BaseModel):
    id: UUID
    slug: str
    title: str
    prompt: str
    difficulty: str
    question_type: str
    topics: list[TopicData]


class QuestionDetail(QuestionSummary):
    intent: str
    answer_outline: list[str]
    common_mistakes: list[str]
    sources: list[SourceData]
    content_markdown: str = ""
    editable: bool = False
    source_document_name: str | None = None


class QuestionImportResult(BaseModel):
    questions: list[QuestionDetail]
    warnings: list[str] = Field(default_factory=list)


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

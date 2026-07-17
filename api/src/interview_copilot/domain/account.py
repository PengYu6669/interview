from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from interview_copilot.domain.auth import UserProfile


class AccountDataSummary(BaseModel):
    account: UserProfile
    draft_count: int
    interview_count: int
    report_count: int
    private_question_count: int
    note_count: int


class ExportDraft(BaseModel):
    id: UUID
    resume_filename: str
    resume_text: str
    jd: str
    target_role: str
    target_company: str
    target_level: str
    interview_round: str
    interview_type: str
    mode: str
    duration_minutes: int
    pressure_level: int
    depth_level: int
    guidance_level: int
    training_focus: str
    source_session_id: UUID | None
    extraction: dict[str, Any] | None
    question_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime


class ExportInterviewTurn(BaseModel):
    sequence: int
    phase_index: int
    question_index: int
    question: str
    answer: str
    answer_mode: str
    decision: str
    rationale: str
    transition: str
    interviewer_reply: str | None
    follow_up_question: str | None
    model: str
    prompt_version: str
    created_at: datetime


class ExportInterviewReport(BaseModel):
    content: dict[str, Any]
    verification_status: str
    verification_error: str | None
    verified_claims: list[dict[str, Any]]
    board_snapshot: dict[str, Any] | None
    coding_evidence: list[dict[str, Any]]
    model: str
    prompt_version: str
    rubric_version: str
    created_at: datetime
    reviews: list["ExportInterviewReportReview"]


class ExportInterviewReportReview(BaseModel):
    id: UUID
    skill_index: int
    skill: str
    original_score: int
    action: str
    reason: str
    status: str
    decision: str | None
    rationale: str | None
    revised_score: int | None
    confidence: float | None
    model: str | None
    prompt_version: str | None
    created_at: datetime
    resolved_at: datetime | None


class ExportInterviewSession(BaseModel):
    id: UUID
    draft_id: UUID
    status: str
    target_role: str
    target_company: str
    target_level: str
    interview_round: str
    interview_type: str
    mode: str
    duration_minutes: int
    pressure_level: int
    depth_level: int
    guidance_level: int
    training_focus: str
    source_session_id: UUID | None
    summary: str
    plan: dict[str, Any]
    model: str
    prompt_version: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    turns: list[ExportInterviewTurn]
    coding_snapshots: list[dict[str, Any]]
    coding_runs: list[dict[str, Any]]
    report: ExportInterviewReport | None


class ExportPrivateQuestion(BaseModel):
    id: UUID
    slug: str
    title: str
    prompt: str
    difficulty: str
    question_type: str
    intent: str
    answer_outline: list[str]
    common_mistakes: list[str]
    content_markdown: str
    source_document_name: str | None
    source_document_id: UUID | None
    framework: str
    evidence: list[dict[str, Any]]
    created_at: datetime


class ExportQuestionDocument(BaseModel):
    id: UUID
    filename: str
    media_type: str
    normalized_text: str
    content_hash: str
    version: int
    status: str
    warnings: list[str]
    coverage_ratio: float
    section_count: int
    covered_section_count: int
    model: str
    prompt_version: str
    created_at: datetime
    updated_at: datetime


class ExportCareerProfile(BaseModel):
    target_role: str
    target_level: str
    target_companies: list[str]
    preferred_cities: list[str]
    weekly_hours: int
    constraints: str
    confirmed_at: datetime
    updated_at: datetime


class ExportWeeklyPlan(BaseModel):
    id: UUID
    week_start: date
    goal: str
    items: list[dict[str, Any]]
    status: str
    created_at: datetime
    updated_at: datetime


class ExportLearningState(BaseModel):
    question_id: UUID
    status: str
    bookmarked: bool
    note: str
    updated_at: datetime
    review_interval_days: int = 0
    review_streak: int = 0
    last_reviewed_at: datetime | None = None
    review_due_at: datetime | None = None


class ExportQuestionMessage(BaseModel):
    role: str
    content: str
    citations: list[dict[str, Any]]
    created_at: datetime


class ExportQuestionConversation(BaseModel):
    id: UUID
    question_id: UUID
    created_at: datetime
    messages: list[ExportQuestionMessage]


class AccountDataExport(BaseModel):
    format_version: str = "account-export-v3"
    exported_at: datetime
    account: UserProfile
    training_drafts: list[ExportDraft]
    interview_sessions: list[ExportInterviewSession]
    private_questions: list[ExportPrivateQuestion]
    question_documents: list[ExportQuestionDocument]
    learning_states: list[ExportLearningState]
    question_conversations: list[ExportQuestionConversation]
    career_profile: ExportCareerProfile | None
    weekly_plans: list[ExportWeeklyPlan]

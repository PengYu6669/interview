from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .board import BoardState
from .training import InterviewRound, InterviewType, TargetLevel

InterviewPhaseKind = Literal[
    "warmup",
    "project",
    "technical",
    "system_design",
    "behavioral",
    "candidate_qa",
]
ReportGenerationStatus = Literal["not_started", "generating", "ready", "failed"]
ReportReviewAction = Literal["reevaluate", "exclude"]
ReportReviewStatus = Literal["pending", "resolved", "failed"]
ReportReviewDecision = Literal["upheld", "revised", "uncertain", "excluded"]
ClaimVerificationResult = Literal["supported", "contradicted", "uncertain"]
ReportVerificationStatus = Literal["completed", "degraded", "not_run"]


class InterviewQuestionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=2_000)
    intent: str = Field(min_length=1, max_length=1_000)
    skills: list[str] = Field(min_length=1, max_length=8)
    follow_up_directions: list[str] = Field(default_factory=list, max_length=5)


class InterviewPhasePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    kind: InterviewPhaseKind = "technical"
    minutes: int = Field(ge=1, le=120)
    skills: list[str] = Field(min_length=1, max_length=12)
    questions: list[InterviewQuestionPlan] = Field(min_length=1, max_length=8)


class InterviewPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_role: str = Field(min_length=1, max_length=150)
    summary: str = Field(min_length=1, max_length=1_000)
    phases: list[InterviewPhasePlan] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def validate_unique_phase_names(self) -> "InterviewPlan":
        names = [phase.name for phase in self.phases]
        if len(names) != len(set(names)):
            raise ValueError("面试阶段名称不能重复")
        return self


class InterviewPhaseSummary(BaseModel):
    name: str
    kind: InterviewPhaseKind
    minutes: int
    skills: list[str]
    question_count: int


class InterviewSessionData(BaseModel):
    id: UUID
    draft_id: UUID
    status: str
    target_role: str
    target_company: str
    target_level: TargetLevel
    interview_round: InterviewRound
    interview_type: InterviewType
    mode: str
    duration_minutes: int
    pressure_level: int = Field(ge=1, le=5)
    depth_level: int = Field(ge=1, le=5)
    guidance_level: int = Field(ge=1, le=5)
    training_focus: str = Field(default="", max_length=500)
    summary: str
    phases: list[InterviewPhaseSummary]
    model: str
    prompt_version: str
    created_at: datetime


class InterviewRuntimeData(BaseModel):
    id: UUID
    status: str
    target_role: str
    target_company: str
    target_level: TargetLevel
    interview_round: InterviewRound
    interview_type: InterviewType
    mode: str
    duration_minutes: int
    pressure_level: int = Field(ge=1, le=5)
    depth_level: int = Field(ge=1, le=5)
    guidance_level: int = Field(ge=1, le=5)
    training_focus: str = Field(default="", max_length=500)
    phases: list[InterviewPhaseSummary]
    current_phase_index: int
    current_question_index: int
    current_question: str | None
    current_question_number: int
    current_question_kind: str = Field(pattern="^(main|follow_up)$")
    follow_up_count: int
    interviewer_transition: str | None = None
    interviewer_reply: str | None = None
    closing_statement: str | None = None
    opening_statement: str
    answered_questions: int
    total_questions: int
    started_at: datetime
    remaining_seconds: int


class InterviewTurnDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern="^(follow_up|next)$")
    follow_up_question: str | None = Field(default=None, max_length=2_000)
    rationale: str = Field(min_length=1, max_length=1_000)
    transition: str = Field(min_length=1, max_length=120)
    interviewer_reply: str | None = Field(default=None, max_length=1_500)

    @model_validator(mode="after")
    def validate_follow_up(self) -> "InterviewTurnDecision":
        if self.action == "follow_up" and not self.follow_up_question:
            raise ValueError("追问决策必须提供追问问题")
        if self.action == "next" and self.follow_up_question:
            raise ValueError("进入下一题时不能附带追问问题")
        return self


class InterviewInterruptionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_interrupt: bool
    reason: str = Field(pattern="^(off_topic|repetitive|vague|none)$")
    transition: str = Field(min_length=1, max_length=120)
    follow_up_question: str | None = Field(default=None, max_length=2_000)
    rationale: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_interruption(self) -> "InterviewInterruptionDecision":
        if self.should_interrupt and not self.follow_up_question:
            raise ValueError("打断回答时必须给出后续问题")
        if not self.should_interrupt and self.reason != "none":
            raise ValueError("不打断时 reason 必须为 none")
        return self


class InterviewHistoryItem(BaseModel):
    id: UUID
    status: str
    target_role: str
    target_company: str
    target_level: TargetLevel
    interview_round: InterviewRound
    interview_type: InterviewType
    mode: str
    duration_minutes: int
    pressure_level: int
    depth_level: int
    guidance_level: int
    answered_questions: int
    total_questions: int
    turn_count: int
    started_at: datetime | None
    completed_at: datetime | None
    report_available: bool
    report_status: ReportGenerationStatus


class InterviewReportGenerationData(BaseModel):
    session_id: UUID
    status: ReportGenerationStatus
    message: str
    started_at: datetime | None
    finished_at: datetime | None


class InterviewSkillScore(BaseModel):
    skill: str = Field(min_length=1, max_length=80)
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    evidence_turns: list[int] = Field(min_length=1, max_length=20)


class InterviewReportFinding(BaseModel):
    skill: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    evidence_turns: list[int] = Field(min_length=1, max_length=20)
    evidence_quote: str = Field(min_length=1, max_length=500)
    analysis: str = Field(min_length=1, max_length=1_000)
    improvement: str | None = Field(default=None, max_length=1_000)


class InterviewReportContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_score: int = Field(ge=0, le=100)
    evidence_coverage: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1, max_length=1_000)
    strengths: list[InterviewReportFinding] = Field(max_length=5)
    improvements: list[InterviewReportFinding] = Field(max_length=5)
    skill_scores: list[InterviewSkillScore] = Field(min_length=1, max_length=12)
    next_training: str = Field(min_length=1, max_length=500)


class InterviewReportReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_request_id: UUID
    skill_index: int = Field(ge=0, le=11)
    action: ReportReviewAction
    reason: str = Field(min_length=10, max_length=1_000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 10:
            raise ValueError("异议理由至少需要 10 个字")
        return normalized


class InterviewReportReviewOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["upheld", "revised", "uncertain"]
    rationale: str = Field(min_length=1, max_length=1_000)
    revised_score: int | None = Field(default=None, ge=0, le=100)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_revised_score(self) -> "InterviewReportReviewOutcome":
        if self.decision == "revised" and self.revised_score is None:
            raise ValueError("修改评分时必须提供 revised_score")
        if self.decision != "revised" and self.revised_score is not None:
            raise ValueError("维持或不确定结论不能提供 revised_score")
        return self


class InterviewReportReviewData(BaseModel):
    id: UUID
    session_id: UUID
    skill_index: int = Field(ge=0)
    skill: str
    original_score: int = Field(ge=0, le=100)
    action: ReportReviewAction
    reason: str
    status: ReportReviewStatus
    decision: ReportReviewDecision | None
    rationale: str | None
    revised_score: int | None = Field(default=None, ge=0, le=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    model: str | None
    prompt_version: str | None
    created_at: datetime
    resolved_at: datetime | None


class VerifiableClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    claim: str = Field(min_length=1, max_length=500)
    evidence_quote: str = Field(min_length=1, max_length=500)


class ClaimVerificationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_index: int = Field(ge=0, le=2)
    result: ClaimVerificationResult
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=1_000)
    citation_indexes: list[int] = Field(default_factory=list, max_length=5)


class VerificationCitation(BaseModel):
    chunk_id: UUID
    title: str = Field(min_length=1, max_length=250)
    quote: str = Field(min_length=1, max_length=1_500)
    version: str | None = Field(default=None, max_length=50)
    source_urls: list[str] = Field(default_factory=list, max_length=10)


class VerifiedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    claim: str = Field(min_length=1, max_length=500)
    evidence_quote: str = Field(min_length=1, max_length=500)
    result: ClaimVerificationResult
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=1_000)
    citations: list[VerificationCitation] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def validate_verification_evidence(self) -> "VerifiedClaim":
        if self.result in {"supported", "contradicted"} and not self.citations:
            raise ValueError("明确核验结论必须包含知识引用")
        if self.result == "contradicted" and self.confidence < 0.8:
            raise ValueError("事实冲突结论的置信度不能低于 0.8")
        return self


class InterviewReportTurn(BaseModel):
    sequence: int = Field(ge=1)
    phase_index: int = Field(ge=0)
    phase_name: str
    question_index: int = Field(ge=0)
    question_number: int = Field(ge=1)
    question: str
    answer: str
    answer_mode: str
    decision: str
    transition: str
    interviewer_reply: str | None
    follow_up_question: str | None
    created_at: datetime


class InterviewReportBoardSnapshot(BaseModel):
    revision: int = Field(ge=0)
    state: BoardState
    created_at: datetime


class InterviewReportData(BaseModel):
    session_id: UUID
    target_role: str
    target_company: str
    target_level: TargetLevel
    interview_round: InterviewRound
    interview_type: InterviewType
    mode: str
    pressure_level: int = Field(ge=1, le=5)
    depth_level: int = Field(ge=1, le=5)
    guidance_level: int = Field(ge=1, le=5)
    session_status: str
    duration_minutes: int
    turn_count: int
    turns: list[InterviewReportTurn]
    board_snapshot: InterviewReportBoardSnapshot | None = None
    content: InterviewReportContent
    reviews: list[InterviewReportReviewData]
    verification_status: ReportVerificationStatus
    verification_error: str | None
    verified_claims: list[VerifiedClaim]
    model: str
    prompt_version: str
    rubric_version: str
    created_at: datetime

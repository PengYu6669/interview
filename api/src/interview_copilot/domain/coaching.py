from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CoachingMode = Literal["structured_expression", "business_sense"]
CoachingChannel = Literal["text", "voice"]
CoachingStatus = Literal["planned", "active", "completed"]
CoachingAction = Literal["follow_up", "retry", "complete"]
CoachingExerciseType = Literal[
    "star_story", "prep_pitch", "structure_puzzle", "decision_simulation", "fermi_estimation"
]
CoachingDifficulty = Literal["guided", "assisted", "pressure"]
CoachingFramework = Literal["star", "prep", "business_decision", "fermi"]
ComparisonChange = Literal["improved", "stable", "regressed", "insufficient"]


class CoachingScaffoldStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=30)
    label: str = Field(min_length=1, max_length=40)
    prompt: str = Field(min_length=1, max_length=200)


class StructurePuzzleFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$", max_length=40)
    text: str = Field(min_length=1, max_length=240)
    target_key: str = Field(min_length=1, max_length=30)
    distractor: bool = False


class StructurePuzzle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=300)
    fragments: list[StructurePuzzleFragment] = Field(min_length=4, max_length=10)


class CoachingScenarioFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=300)
    source_type: Literal["virtual", "curated"] = "virtual"
    source_label: str | None = Field(default=None, max_length=160)


class CoachingSourceQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str = Field(min_length=1, max_length=250)
    prompt: str = Field(min_length=1, max_length=2_000)
    framework: Literal["technical", "star", "prep", "system_design"]
    evidence_quotes: list[str] = Field(default_factory=list, max_length=8)


class CoachingTaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=500)
    scenario: str = Field(min_length=1, max_length=3_000)
    primary_question: str = Field(min_length=1, max_length=1_500)
    estimated_minutes: int = Field(ge=5, le=30)
    dimensions: list[str] = Field(min_length=2, max_length=8)
    exercise_type: CoachingExerciseType = "star_story"
    framework: CoachingFramework = "star"
    difficulty: CoachingDifficulty = "guided"
    time_limit_seconds: int = Field(default=180, ge=60, le=900)
    target_dimension: str = Field(default="conclusion", min_length=1, max_length=60)
    scaffold: list[CoachingScaffoldStep] = Field(default_factory=list, max_length=8)
    puzzle: StructurePuzzle | None = None
    scenario_version: str = Field(default="generated-v1", min_length=1, max_length=80)
    facts: list[CoachingScenarioFact] = Field(default_factory=list, max_length=12)
    constraint_change: str | None = Field(default=None, max_length=500)
    source_questions: list[CoachingSourceQuestion] = Field(default_factory=list, max_length=20)


class DimensionAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=60)
    status: Literal["observed", "evidence_insufficient"]
    level: int | None = Field(
        ge=1,
        le=5,
        description="status=observed 时为 1 至 5；status=evidence_insufficient 时必须为 null",
    )
    evidence_quote: str | None = Field(
        max_length=500,
        description="status=observed 时逐字引用用户回答；证据不足时必须为 null",
    )
    feedback: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_evidence(self) -> "DimensionAssessment":
        if self.status == "observed" and (self.level is None or not self.evidence_quote):
            raise ValueError("已观察维度必须包含等级和回答证据")
        if self.status == "evidence_insufficient" and (
            self.level is not None or self.evidence_quote is not None
        ):
            raise ValueError("证据不足时不能给出等级或伪造证据")
        return self


class CoachingEvidenceSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=60)
    label: str = Field(min_length=1, max_length=80)
    evidence_quote: str = Field(min_length=1, max_length=500)


class CoachingPriorityGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(min_length=1, max_length=60)
    diagnosis: str = Field(min_length=1, max_length=300)
    retry_prompt: str = Field(min_length=1, max_length=300)


class CoachingComparisonItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(min_length=1, max_length=60)
    change: ComparisonChange
    before_level: int | None = Field(default=None, ge=1, le=5)
    after_level: int | None = Field(default=None, ge=1, le=5)
    before_quote: str | None = Field(default=None, max_length=500)
    after_quote: str | None = Field(default=None, max_length=500)
    explanation: str = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def validate_change_evidence(self) -> "CoachingComparisonItem":
        if self.change == "insufficient":
            return self
        if (
            self.before_level is None
            or self.after_level is None
            or not self.before_quote
            or not self.after_quote
        ):
            self.change = "insufficient"
            self.before_level = None
            self.after_level = None
            return self
        if self.after_level > self.before_level:
            self.change = "improved"
        elif self.after_level < self.before_level:
            self.change = "regressed"
        else:
            self.change = "stable"
        return self


class CoachingAttemptComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CoachingComparisonItem] = Field(min_length=1, max_length=8)
    overall_summary: str = Field(min_length=1, max_length=600)


class CoachingNextPractice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    focus: str = Field(min_length=1, max_length=300)
    recommended_difficulty: CoachingDifficulty
    estimated_minutes: int = Field(default=10, ge=5, le=20)


class CoachingDeliveryMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["voice_transcript", "text"]
    character_count: int = Field(ge=0, le=20_000)
    characters_per_minute: int | None = Field(default=None, ge=0, le=20_000)
    filler_counts: dict[str, int] = Field(default_factory=dict)
    filler_total: int = Field(ge=0)


class CoachingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: CoachingAction
    coach_reply: str = Field(min_length=1, max_length=1_000)
    next_question: str | None = Field(default=None, max_length=1_500)
    assessments: list[DimensionAssessment] = Field(min_length=1, max_length=8)
    summary: str = Field(min_length=1, max_length=1_000)
    evidence_segments: list[CoachingEvidenceSegment] = Field(default_factory=list, max_length=12)
    priority_gaps: list[CoachingPriorityGap] = Field(default_factory=list, max_length=2)
    comparison: CoachingAttemptComparison | None = None
    next_practice: CoachingNextPractice | None = None
    delivery_metrics: CoachingDeliveryMetrics | None = None

    @field_validator("evidence_segments", "priority_gaps", mode="before")
    @classmethod
    def normalize_optional_lists(cls, value: object) -> object:
        return [] if value is None else value

    @model_validator(mode="after")
    def validate_next_question(self) -> "CoachingDecision":
        if self.action == "complete" and self.next_question is not None:
            raise ValueError("训练完成后不能继续提问")
        if self.action != "complete" and not self.next_question:
            raise ValueError("继续训练时必须给出下一个问题")
        return self


class CoachingTurnData(BaseModel):
    id: UUID
    sequence: int
    answer: str
    answer_mode: CoachingChannel
    attempt_number: int = Field(default=1, ge=1, le=3)
    elapsed_seconds: int | None = Field(default=None, ge=0, le=3_600)
    decision: CoachingDecision
    created_at: datetime


class CoachingSessionData(BaseModel):
    id: UUID
    mode: CoachingMode
    channel: CoachingChannel
    status: CoachingStatus
    target_role: str
    training_goal: str
    skill_name: str
    skill_version: str
    task: CoachingTaskPlan
    current_question: str | None
    turns: list[CoachingTurnData]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    career_plan_item_id: UUID | None = None


class CoachingSessionSummary(BaseModel):
    id: UUID
    mode: CoachingMode
    channel: CoachingChannel
    status: CoachingStatus
    title: str
    target_role: str
    current_question: str | None
    turn_count: int = Field(ge=0)
    exercise_type: CoachingExerciseType = "star_story"
    difficulty: CoachingDifficulty = "guided"
    updated_at: datetime

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

CodingLanguage = Literal["python"]
CodingRunStatus = Literal[
    "passed",
    "failed",
    "compile_error",
    "runtime_error",
    "timed_out",
    "output_limit",
    "memory_limit",
]


class CodingTestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    arguments: list[JsonValue] = Field(default_factory=list, max_length=8)
    expected: JsonValue


class CodingProblemSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=2_000)
    language: CodingLanguage = "python"
    entrypoint: Literal["solve"] = "solve"
    starter_code: str = Field(min_length=1, max_length=4_000)
    constraints: list[str] = Field(default_factory=list, max_length=10)
    public_tests: list[CodingTestCase] = Field(min_length=1, max_length=8)


class CodingSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_snapshot_id: UUID
    base_revision: int = Field(ge=0)
    source: str = Field(min_length=1, max_length=20_000)
    complexity_notes: str = Field(default="", max_length=2_000)


class CodingSnapshotData(BaseModel):
    id: UUID
    session_id: UUID
    phase_index: int = Field(ge=0)
    question_index: int = Field(ge=0)
    revision: int = Field(ge=0)
    client_snapshot_id: UUID
    source: str
    complexity_notes: str
    created_at: datetime


class CodingWorkspaceData(BaseModel):
    problem: CodingProblemSpec
    snapshot: CodingSnapshotData | None


class CodingRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_request_id: UUID
    snapshot_revision: int = Field(ge=0)


class CodingTestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool
    expected: JsonValue
    actual: JsonValue | str | None = None
    error: str | None = Field(default=None, max_length=1_000)
    stdout: str = Field(default="", max_length=4_000)
    duration_ms: int = Field(ge=0)


class CodingExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CodingRunStatus
    tests: list[CodingTestResult] = Field(default_factory=list, max_length=8)
    duration_ms: int = Field(ge=0)
    error: str | None = Field(default=None, max_length=1_000)


class CodingRunData(CodingExecutionResult):
    id: UUID
    session_id: UUID
    snapshot_id: UUID
    client_request_id: UUID
    created_at: datetime


class CodingReportRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CodingRunStatus
    snapshot_revision: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    created_at: datetime


class CodingReportEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase_index: int = Field(ge=0)
    question_index: int = Field(ge=0)
    problem: CodingProblemSpec
    latest_source: str
    complexity_notes: str
    snapshot_count: int = Field(ge=1, le=100)
    runs: list[CodingReportRunSummary] = Field(default_factory=list, max_length=100)

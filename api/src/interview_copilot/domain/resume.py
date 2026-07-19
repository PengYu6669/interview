from pydantic import BaseModel, ConfigDict, Field

RESUME_SCHEMA_VERSION = "1.1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceItem(StrictModel):
    value: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=1, max_length=1000)


class ProjectMetric(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=100)
    evidence: str = Field(min_length=1, max_length=500)


class ResumeProject(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=600)
    technologies: list[EvidenceItem] = Field(default_factory=list, max_length=8)
    metrics: list[ProjectMetric] = Field(default_factory=list, max_length=8)
    evidence: str = Field(min_length=1, max_length=800)


class WorkExperience(StrictModel):
    organization: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=150)
    period: str | None = Field(default=None, max_length=100)
    highlights: list[EvidenceItem] = Field(default_factory=list, max_length=6)
    evidence: str = Field(min_length=1, max_length=800)


class EducationExperience(StrictModel):
    institution: str = Field(min_length=1, max_length=200)
    major: str | None = Field(default=None, max_length=150)
    degree: str | None = Field(default=None, max_length=100)
    period: str | None = Field(default=None, max_length=100)
    evidence: str = Field(min_length=1, max_length=1000)


class ResumeProfile(StrictModel):
    schema_version: str = RESUME_SCHEMA_VERSION
    target_role: str = Field(min_length=1, max_length=150)
    summary: str = Field(default="", max_length=300)
    skills: list[EvidenceItem] = Field(default_factory=list, max_length=15)
    projects: list[ResumeProject] = Field(default_factory=list, max_length=10)
    work_experiences: list[WorkExperience] = Field(default_factory=list, max_length=10)
    education: list[EducationExperience] = Field(default_factory=list, max_length=6)
    jd_requirements: list[EvidenceItem] = Field(default_factory=list, max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=15)


class ResumeExtractionResult(StrictModel):
    profile: ResumeProfile
    model: str = Field(min_length=1, max_length=100)
    prompt_version: str = Field(min_length=1, max_length=50)

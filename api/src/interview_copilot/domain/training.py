from typing import Literal

from pydantic import BaseModel, Field

TargetLevel = Literal["intern", "campus", "mid", "senior"]
InterviewRound = Literal["first", "second", "final", "manager"]
InterviewType = Literal[
    "comprehensive",
    "project",
    "technical",
    "system_design",
    "behavioral",
    "weak_area",
]


class TrainingContext(BaseModel):
    target_company: str = Field(default="", max_length=100)
    target_level: TargetLevel = "campus"
    interview_round: InterviewRound = "first"
    interview_type: InterviewType = "comprehensive"

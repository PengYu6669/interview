import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    mode: str
    exercise_type: str
    difficulty: str
    target_role: str
    training_goal: str
    answers: list[str] = Field(min_length=2, max_length=2)
    expected_framework: str
    requires_same_question_retry: bool
    max_priority_gaps: int = Field(ge=1, le=2)
    requires_exact_answer_evidence: bool


def test_coaching_evaluation_dataset_is_versioned_and_covers_both_skills() -> None:
    path = Path(__file__).parents[1] / "evaluations" / "coaching_skill_cases.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [EvaluationCase.model_validate(item) for item in payload["cases"]]

    assert payload["dataset_version"] == "coaching-skill-eval-v1"
    assert payload["skill_versions"] == {
        "structured-expression-coach": "2.0.0",
        "business-sense-coach": "2.0.0",
    }
    assert {item.mode for item in cases} == {"structured_expression", "business_sense"}
    assert all(item.requires_same_question_retry for item in cases)
    assert all(item.requires_exact_answer_evidence for item in cases)

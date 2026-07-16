import json
from pathlib import Path


def test_career_planning_dataset_is_versioned_and_bounded() -> None:
    path = Path(__file__).parents[1] / "evaluations" / "career_planning_cases.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["dataset_version"] == "career-planning-eval-v1"
    assert payload["skill_version"] == "1.1.0"
    assert len(payload["cases"]) == 2
    assert all(1 <= item["profile"]["weekly_hours"] <= 8 for item in payload["cases"])

from pathlib import Path


def test_week_start_uses_local_calendar_date() -> None:
    source = (
        Path(__file__).parents[2]
        / "web"
        / "src"
        / "features"
        / "growth"
        / "career-planner.tsx"
    ).read_text(encoding="utf-8")

    monday_helper = source.split("function mondayValue()", maxsplit=1)[1].split(
        "function detail", maxsplit=1
    )[0]
    assert "getFullYear()" in monday_helper
    assert "getMonth()" in monday_helper
    assert "getDate()" in monday_helper
    assert "toISOString()" not in monday_helper


def test_missing_completed_career_draft_falls_back_to_saved_plan() -> None:
    source = (
        Path(__file__).parents[2]
        / "web"
        / "src"
        / "features"
        / "growth"
        / "career-planner.tsx"
    ).read_text(encoding="utf-8")

    assert "readDraft(latestJob.resource_id, true)" in source
    assert "response.status === 404 || response.status === 422" in source
    assert "if (!draft) return" in source

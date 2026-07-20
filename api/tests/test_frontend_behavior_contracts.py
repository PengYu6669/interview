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


def test_training_hero_uses_available_text_width() -> None:
    source = (
        Path(__file__).parents[2]
        / "web"
        / "src"
        / "features"
        / "training"
        / "training-hub.tsx"
    ).read_text(encoding="utf-8")

    assert 'className="mt-3 w-full text-2xl' in source
    assert "max-w-[40rem] text-balance" not in source


def test_terminal_question_import_status_is_dismissed() -> None:
    source = (
        Path(__file__).parents[2]
        / "web"
        / "src"
        / "features"
        / "questions"
        / "question-bank.tsx"
    ).read_text(encoding="utf-8")

    assert 'if (!["queued", "processing"].includes(job.status)) return' in source
    assert 'importJob.status === "completed" ? 5_000 : 10_000' in source
    assert 'aria-label="关闭资料处理状态"' in source

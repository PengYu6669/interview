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


def test_resume_review_keeps_source_visible_and_matches_panel_height() -> None:
    root = Path(__file__).parents[2] / "web" / "src"
    page = (root / "app" / "review" / "page.tsx").read_text(encoding="utf-8")
    styles = (root / "app" / "globals.css").read_text(encoding="utf-8")

    assert 'className="review-block resume-source-block"' in page
    assert 'className="mt-5"><StructuredProfile' in page
    assert "align-items:stretch" in styles
    assert ".source-preview{display:block" in styles
    assert ".source-preview{display:none}" not in styles


def test_blueprint_errors_include_backend_request_id() -> None:
    source = (
        Path(__file__).parents[2]
        / "web"
        / "src"
        / "features"
        / "interview-blueprint"
        / "interview-blueprint.tsx"
    ).read_text(encoding="utf-8")

    assert '"request_id" in payload' in source
    assert "请求编号" in source


def test_admin_navigation_only_exposes_management_modules() -> None:
    root = Path(__file__).parents[2] / "web" / "src"
    header = (root / "components" / "site-header.tsx").read_text(encoding="utf-8")
    assert '"/admin/questions"' in header
    assert '"/admin/users"' in header
    assert '"/admin/logs"' in header
    assert "user?.role === \"admin\" ? adminNavigation : navigation" in header
    assert "adminNavigation" in header


def test_interview_interruption_fails_open_and_recording_uses_wall_clock() -> None:
    root = Path(__file__).parents[2] / "web" / "src"
    room = (
        root / "features" / "interview-room" / "interview-room.tsx"
    ).read_text(encoding="utf-8")
    route = (
        root
        / "app"
        / "api"
        / "interview-sessions"
        / "[sessionId]"
        / "interruptions"
        / "route.ts"
    ).read_text(encoding="utf-8")
    styles = (root / "app" / "globals.css").read_text(encoding="utf-8")

    assert "Date.now() - startedAt" in room
    assert "recordingElapsedRef.current += 1" not in room
    assert "Math.min(55, Math.max(12, recordingElapsedRef.current))" in room
    assert 'NextResponse.json({ interrupted: false })' in route
    assert "AbortSignal.timeout(15_000)" in route
    assert ".feishu-room .hangup-button:disabled" in styles


def test_homepage_matches_current_interview_experience() -> None:
    source = (
        Path(__file__).parents[2] / "web" / "src" / "app" / "page.tsx"
    ).read_text(encoding="utf-8")

    assert "沉浸式 AI 模拟面试" in source
    assert "实时语音追问" in source
    assert "中断可以恢复" in source
    assert "AI 工作轨迹" not in source
    assert "grayscale contrast-125" in source

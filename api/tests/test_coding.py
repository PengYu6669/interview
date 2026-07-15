import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.coding import CodingConflictError, InterviewCodingService
from interview_copilot.domain.coding import (
    CodingExecutionResult,
    CodingProblemSpec,
    CodingRunRequest,
    CodingSnapshotRequest,
    CodingTestCase,
)
from interview_copilot.domain.interviews import (
    InterviewPhasePlan,
    InterviewPlan,
    InterviewQuestionPlan,
)
from interview_copilot.infrastructure.coding import (  # noqa: F401
    InterviewCodingRunRecord,
    InterviewCodingSnapshotRecord,
)
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.drafts import TrainingDraftRecord
from interview_copilot.infrastructure.interviews import InterviewSessionRecord
from interview_copilot.infrastructure.questions import QuestionRecord  # noqa: F401
from interview_copilot.sandbox.docker_python import (
    DockerPythonSandbox,
    DockerPythonSandboxConfig,
)

IMAGE = (
    "python:3.12.11-alpine3.22@sha256:"
    "efcdfa6a6b2fd2afb9c7dfa9a5b288a6f68338b5cfdebe6b637d986067d85757"
)


class FakeExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, **_: object) -> CodingExecutionResult:
        self.calls += 1
        return CodingExecutionResult(status="passed", tests=[], duration_ms=12)


def _problem() -> CodingProblemSpec:
    return CodingProblemSpec(
        title="两数之和",
        description="返回数组中和为目标值的两个下标。",
        starter_code="def solve(nums, target):\n    pass\n",
        constraints=["数组长度不超过 1000"],
        public_tests=[
            CodingTestCase(name="基础样例", arguments=[[2, 7, 11, 15], 9], expected=[0, 1])
        ],
    )


def _session(db: Session) -> tuple[UserRecord, InterviewSessionRecord]:
    user = UserRecord(
        username="coding-owner",
        email="coding@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
    )
    db.add(user)
    db.flush()
    draft = TrainingDraftRecord(
        user_id=user.id,
        resume_filename="resume.pdf",
        resume_text="候选人材料",
        jd="Python 后端岗位",
        target_role="Python 后端工程师",
        target_company="",
        target_level="campus",
        interview_round="first",
        interview_type="coding",
        mode="standard",
        duration_minutes=20,
        pressure_level=3,
        depth_level=3,
        guidance_level=2,
        training_focus="",
        extraction={"schema_version": "test"},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(draft)
    db.flush()
    plan = InterviewPlan(
        target_role="Python 后端工程师",
        summary="算法专项",
        phases=[
            InterviewPhasePlan(
                name="算法题",
                kind="coding",
                minutes=18,
                skills=["算法"],
                questions=[
                    InterviewQuestionPlan(
                        prompt="实现两数之和。",
                        intent="考察哈希表",
                        skills=["哈希表"],
                        coding_spec=_problem(),
                    )
                ],
            ),
            InterviewPhasePlan(
                name="反问",
                kind="candidate_qa",
                minutes=2,
                skills=["沟通"],
                questions=[
                    InterviewQuestionPlan(
                        prompt="你有什么想了解的吗？",
                        intent="双向沟通",
                        skills=["沟通"],
                    )
                ],
            ),
        ],
    )
    interview = InterviewSessionRecord(
        user_id=user.id,
        draft_id=draft.id,
        status="started",
        target_role="Python 后端工程师",
        duration_minutes=20,
        mode="standard",
        summary="算法专项",
        plan=plan.model_dump(mode="json"),
        model="fake",
        prompt_version="test",
        current_phase_index=0,
        current_question_index=0,
        created_at=datetime.now(UTC),
    )
    db.add(interview)
    db.commit()
    return user, interview


@pytest.mark.asyncio
async def test_coding_workspace_is_versioned_and_run_is_idempotent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user, interview = _session(db)
        executor = FakeExecutor()
        service = InterviewCodingService(db, executor)
        request = CodingSnapshotRequest(
            client_snapshot_id=uuid4(),
            base_revision=0,
            source="def solve(nums, target):\n    return [0, 1]\n",
            complexity_notes="时间 O(n)，空间 O(n)。",
        )
        saved = service.save(user_id=user.id, session_id=interview.id, request=request)
        repeated = service.save(user_id=user.id, session_id=interview.id, request=request)

        assert saved.snapshot is not None
        assert repeated.snapshot is not None
        assert saved.snapshot.id == repeated.snapshot.id
        assert saved.snapshot.revision == 0
        with pytest.raises(CodingConflictError):
            service.save(
                user_id=user.id,
                session_id=interview.id,
                request=CodingSnapshotRequest(
                    client_snapshot_id=uuid4(),
                    base_revision=0,
                    source=request.source,
                ),
            )
        run_request = CodingRunRequest(
            client_request_id=uuid4(), snapshot_revision=saved.snapshot.revision
        )
        first_run = await service.run(
            user_id=user.id, session_id=interview.id, request=run_request
        )
        repeated_run = await service.run(
            user_id=user.id, session_id=interview.id, request=run_request
        )

        assert first_run.status == "passed"
        assert repeated_run.id == first_run.id
        assert executor.calls == 1


def _docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    result = subprocess.run(
        ["docker", "image", "inspect", IMAGE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


@pytest.mark.skipif(not _docker_ready(), reason="本机没有准备 Coding 沙箱镜像")
@pytest.mark.asyncio
async def test_docker_sandbox_passes_tests_and_blocks_network() -> None:
    sandbox = DockerPythonSandbox(
        DockerPythonSandboxConfig(image=IMAGE, timeout_seconds=3)
    )
    passed = await sandbox.execute(
        source="def solve(nums, target):\n    return [0, 1]\n",
        problem=_problem(),
    )
    blocked = await sandbox.execute(
        source=(
            "def solve(nums, target):\n"
            "    import socket\n"
            "    socket.create_connection(('1.1.1.1', 53), timeout=0.1)\n"
            "    return [0, 1]\n"
        ),
        problem=_problem(),
    )

    assert passed.status == "passed"
    assert passed.tests[0].passed is True
    assert blocked.status == "runtime_error"
    assert blocked.tests[0].passed is False


@pytest.mark.skipif(not _docker_ready(), reason="本机没有准备 Coding 沙箱镜像")
@pytest.mark.asyncio
async def test_docker_sandbox_stops_infinite_loop() -> None:
    sandbox = DockerPythonSandbox(
        DockerPythonSandboxConfig(image=IMAGE, timeout_seconds=1)
    )
    result = await sandbox.execute(
        source="def solve(nums, target):\n    while True:\n        pass\n",
        problem=_problem(),
    )

    assert result.status == "timed_out"

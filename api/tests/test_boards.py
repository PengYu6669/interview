from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.boards import BoardConflictError, InterviewBoardService
from interview_copilot.domain.board import (
    BoardEdge,
    BoardNode,
    BoardSnapshotRequest,
    BoardState,
)
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.drafts import TrainingDraftRecord  # noqa: F401
from interview_copilot.infrastructure.interviews import InterviewSessionRecord
from interview_copilot.infrastructure.questions import QuestionRecord  # noqa: F401


def _database() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _session(
    session: Session, *, kind: str = "system_design"
) -> tuple[UserRecord, InterviewSessionRecord]:
    user = UserRecord(
        username=f"board-{uuid4().hex[:8]}",
        email=f"board-{uuid4().hex[:8]}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.flush()
    now = datetime.now(UTC)
    draft = TrainingDraftRecord(
        user_id=user.id,
        resume_filename="board.md",
        resume_text="board test",
        jd="system design",
        target_role="后端工程师",
        mode="normal",
        duration_minutes=20,
        pressure_level=3,
        depth_level=4,
        guidance_level=2,
        extraction={"schema_version": "test"},
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(days=7),
    )
    session.add(draft)
    session.flush()
    record = InterviewSessionRecord(
        user_id=user.id,
        draft_id=draft.id,
        status="started",
        target_role="后端工程师",
        mode="normal",
        duration_minutes=20,
        pressure_level=3,
        depth_level=4,
        guidance_level=2,
        summary="系统设计",
        plan={
            "target_role": "后端工程师",
            "summary": "系统设计",
            "phases": [
                {
                    "name": "系统设计",
                    "kind": kind,
                    "minutes": 20,
                    "skills": ["架构"],
                    "questions": [
                        {
                            "prompt": "请设计系统",
                            "intent": "考察架构",
                            "skills": ["架构"],
                            "follow_up_directions": [],
                        }
                    ],
                },
                {
                    "name": "结束",
                    "kind": "candidate_qa",
                    "minutes": 1,
                    "skills": ["沟通"],
                    "questions": [
                        {
                            "prompt": "还有问题吗",
                            "intent": "反问",
                            "skills": ["沟通"],
                            "follow_up_directions": [],
                        }
                    ],
                },
            ],
        },
        model="test",
        prompt_version="test",
        current_phase_index=0,
        current_question_index=0,
        started_at=now,
        created_at=now,
        active_question="请设计系统",
    )
    session.add(record)
    session.commit()
    return user, record


def _state() -> BoardState:
    client_id = uuid4()
    service_id = uuid4()
    return BoardState(
        nodes=[
            BoardNode(
                id=client_id, kind="client", label="客户端", x=80, y=120, width=160, height=72
            ),
            BoardNode(
                id=service_id, kind="service", label="面试服务", x=420, y=120, width=180, height=72
            ),
        ],
        edges=[
            BoardEdge(id=uuid4(), source_id=client_id, target_id=service_id, label="HTTPS"),
        ],
        annotations=[],
    )


def test_board_snapshot_is_idempotent_and_versioned() -> None:
    with _database() as session:
        user, interview = _session(session)
        service = InterviewBoardService(session)
        request = BoardSnapshotRequest(
            client_snapshot_id=uuid4(),
            base_revision=0,
            state=_state(),
        )

        first = service.save(user_id=user.id, session_id=interview.id, request=request)
        repeated = service.save(user_id=user.id, session_id=interview.id, request=request)

        assert first.revision == 0
        assert repeated.id == first.id
        assert service.get_latest(user_id=user.id, session_id=interview.id) == first


def test_board_rejects_stale_revision_and_wrong_stage() -> None:
    with _database() as session:
        user, interview = _session(session)
        service = InterviewBoardService(session)
        service.save(
            user_id=user.id,
            session_id=interview.id,
            request=BoardSnapshotRequest(
                client_snapshot_id=uuid4(), base_revision=0, state=_state()
            ),
        )
        with pytest.raises(BoardConflictError) as conflict:
            service.save(
                user_id=user.id,
                session_id=interview.id,
                request=BoardSnapshotRequest(
                    client_snapshot_id=uuid4(), base_revision=0, state=_state()
                ),
            )
        assert conflict.value.current.revision == 0

        interview.plan["phases"][0]["kind"] = "technical"
        session.commit()
        with pytest.raises(ValueError, match="系统设计阶段"):
            service.save(
                user_id=user.id,
                session_id=interview.id,
                request=BoardSnapshotRequest(
                    client_snapshot_id=uuid4(), base_revision=1, state=_state()
                ),
            )


def test_board_validates_edge_references() -> None:
    with pytest.raises(ValueError, match="已存在的组件"):
        BoardState(
            nodes=[
                BoardNode(id=uuid4(), kind="service", label="服务", x=0, y=0, width=120, height=56)
            ],
            edges=[BoardEdge(id=uuid4(), source_id=uuid4(), target_id=uuid4())],
        )

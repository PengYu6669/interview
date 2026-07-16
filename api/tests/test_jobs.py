from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.jobs import AiJobService
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.jobs import AiJobRecord


def _user(session: Session, name: str) -> UserRecord:
    user = UserRecord(
        username=name,
        email=f"{name}@example.com",
        password_hash="hash",
        created_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def test_ai_job_deduplicates_active_kind_and_tracks_completion() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "job-owner")
        service = AiJobService(session)

        first, created = service.create(
            user_id=owner.id,
            kind="question_import",
            stage="等待解析资料",
            estimated_seconds=70,
        )
        duplicate, duplicate_created = service.create(
            user_id=owner.id,
            kind="question_import",
            stage="等待解析资料",
            estimated_seconds=70,
        )

        assert created is True
        assert duplicate_created is False
        assert duplicate.id == first.id
        record = session.get(AiJobRecord, first.id)
        assert record is not None
        service.update(record, stage="正在生成题目", progress=60)
        service.complete(record, resource_id=owner.id)
        completed = service.get(user_id=owner.id, job_id=first.id)
        assert completed.status == "completed"
        assert completed.progress == 100
        assert completed.resource_id == owner.id


def test_ai_job_rejects_cross_user_access() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "job-owner-two")
        stranger = _user(session, "job-stranger")
        job, _ = AiJobService(session).create(
            user_id=owner.id,
            kind="career_plan",
            stage="等待规划",
            estimated_seconds=60,
        )

        with pytest.raises(LookupError, match="找不到"):
            AiJobService(session).get(user_id=stranger.id, job_id=job.id)

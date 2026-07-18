from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.jobs import HARD_TIMEOUT, AiJobService
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


def test_worker_claims_queued_job_and_persists_payload() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "worker-owner")
        service = AiJobService(session)
        created, _ = service.create(
            user_id=owner.id,
            kind="question_import",
            stage="等待处理",
            estimated_seconds=240,
            payload={"action": "import", "question_limit": 30},
        )

        claimed = service.claim_next(kind="question_import")

        assert claimed is not None
        assert claimed.id == created.id
        assert claimed.payload["question_limit"] == 30
        assert claimed.attempt_count == 1
        assert claimed.heartbeat_at is not None


def test_expire_stale_fails_timed_out_processing_job() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "stale-owner")
        service = AiJobService(session)
        job, _ = service.create(
            user_id=owner.id,
            kind="question_import",
            stage="正在分析知识点",
            estimated_seconds=240,
        )
        record = session.get(AiJobRecord, job.id)
        assert record is not None
        record.status = "processing"
        record.progress = 50
        # Older than hard timeout and without a recent heartbeat.
        record.created_at = datetime.now(UTC) - HARD_TIMEOUT - timedelta(minutes=1)
        record.heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
        record.updated_at = record.heartbeat_at
        session.commit()

        expired = service.expire_stale(kind="question_import")
        refreshed = service.get(user_id=owner.id, job_id=job.id)

        assert expired == 1
        assert refreshed.status == "failed"
        assert "超时" in (refreshed.error or "")


def test_create_expires_blocking_active_job() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = _user(session, "block-owner")
        service = AiJobService(session)
        stuck, _ = service.create(
            user_id=owner.id,
            kind="question_import",
            stage="卡住",
            estimated_seconds=60,
        )
        record = session.get(AiJobRecord, stuck.id)
        assert record is not None
        record.status = "processing"
        record.created_at = datetime.now(UTC) - timedelta(hours=2)
        record.heartbeat_at = datetime.now(UTC) - timedelta(hours=1)
        session.commit()

        replacement, created = service.create(
            user_id=owner.id,
            kind="question_import",
            stage="等待解析资料",
            estimated_seconds=120,
        )

        assert created is True
        assert replacement.id != stuck.id
        assert service.get(user_id=owner.id, job_id=stuck.id).status == "failed"

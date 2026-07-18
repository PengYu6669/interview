from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from interview_copilot.domain.jobs import AiJobStatus
from interview_copilot.infrastructure.jobs import AiJobRecord

ACTIVE_STATUSES = {"queued", "processing"}


class AiJobService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        user_id: UUID,
        kind: str,
        stage: str,
        estimated_seconds: int,
        payload: dict | None = None,
    ) -> tuple[AiJobStatus, bool]:
        active = self._session.scalar(
            select(AiJobRecord)
            .where(
                AiJobRecord.user_id == user_id,
                AiJobRecord.kind == kind,
                AiJobRecord.status.in_(ACTIVE_STATUSES),
            )
            .order_by(AiJobRecord.created_at.desc())
        )
        if active:
            return self._domain(active), False
        now = datetime.now(UTC)
        record = AiJobRecord(
            id=uuid4(),
            user_id=user_id,
            kind=kind,
            status="queued",
            stage=stage,
            progress=2,
            estimated_seconds=estimated_seconds,
            payload=payload or {},
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        self._session.commit()
        return self._domain(record), True

    def get(self, *, user_id: UUID, job_id: UUID) -> AiJobStatus:
        record = self._session.scalar(
            select(AiJobRecord).where(AiJobRecord.id == job_id, AiJobRecord.user_id == user_id)
        )
        if not record:
            raise LookupError("找不到这项后台任务")
        return self._domain(record)

    def latest(self, *, user_id: UUID, kind: str) -> AiJobStatus | None:
        record = self._session.scalar(
            select(AiJobRecord)
            .where(AiJobRecord.user_id == user_id, AiJobRecord.kind == kind)
            .order_by(AiJobRecord.created_at.desc())
        )
        if not record:
            return None
        return self.get(user_id=user_id, job_id=record.id)

    def update(
        self,
        record: AiJobRecord,
        *,
        stage: str,
        progress: int,
        resource_id: UUID | None = None,
    ) -> None:
        record.status = "processing"
        record.stage = stage[:80]
        record.progress = max(2, min(95, progress))
        record.updated_at = datetime.now(UTC)
        record.heartbeat_at = record.updated_at
        if resource_id:
            record.resource_id = resource_id
        self._session.commit()

    def claim_next(self, *, kind: str) -> AiJobRecord | None:
        # One process owns the question worker lease even if the host starts duplicate workers.
        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            lock = self._session.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": 781204}
            ).scalar()
        else:
            lock = True
        if not lock:
            self._session.rollback()
            return None
        stale_before = datetime.now(UTC) - timedelta(minutes=3)
        record = self._session.scalar(
            select(AiJobRecord)
            .where(
                AiJobRecord.kind == kind,
                (
                    (AiJobRecord.status == "queued")
                    | (
                        (AiJobRecord.status == "processing")
                        & (
                            AiJobRecord.heartbeat_at.is_(None)
                            | (AiJobRecord.heartbeat_at < stale_before)
                        )
                    )
                ),
            )
            .order_by(AiJobRecord.created_at)
            .with_for_update(skip_locked=True)
        )
        if not record:
            if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
                self._session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": 781204})
            self._session.commit()
            return None
        record.status = "processing"
        record.stage = "正在恢复任务" if record.attempt_count else record.stage
        record.attempt_count += 1
        record.heartbeat_at = datetime.now(UTC)
        record.updated_at = record.heartbeat_at
        self._session.commit()
        return record

    def release_worker_lease(self) -> None:
        if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
            self._session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": 781204})
        self._session.commit()

    def complete(self, record: AiJobRecord, *, resource_id: UUID) -> None:
        now = datetime.now(UTC)
        record.status = "completed"
        record.stage = "处理完成"
        record.progress = 100
        record.resource_id = resource_id
        record.error = None
        record.updated_at = now
        record.completed_at = now
        self._session.commit()

    def fail(self, record: AiJobRecord, error: str) -> None:
        now = datetime.now(UTC)
        record.status = "failed"
        record.stage = "处理失败"
        record.error = error[:500]
        record.updated_at = now
        record.completed_at = now
        self._session.commit()

    @staticmethod
    def _domain(record: AiJobRecord) -> AiJobStatus:
        return AiJobStatus.model_validate(record, from_attributes=True)

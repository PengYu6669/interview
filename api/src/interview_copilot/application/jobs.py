from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from interview_copilot.domain.jobs import AiJobStatus
from interview_copilot.infrastructure.jobs import AiJobRecord

ACTIVE_STATUSES = {"queued", "processing"}
# Absolute ceiling keeps a hung LLM call from blocking new imports forever.
HARD_TIMEOUT = timedelta(minutes=20)
# No progress/heartbeat for this long means the worker is dead or blocked.
# LLM batches can take a few minutes without intermediate progress callbacks.
STALE_HEARTBEAT = timedelta(minutes=8)


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
        self.expire_stale(user_id=user_id, kind=kind)
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
        self._expire_if_stale(record)
        return self._domain(record)

    def latest(self, *, user_id: UUID, kind: str) -> AiJobStatus | None:
        self.expire_stale(user_id=user_id, kind=kind)
        record = self._session.scalar(
            select(AiJobRecord)
            .where(AiJobRecord.user_id == user_id, AiJobRecord.kind == kind)
            .order_by(AiJobRecord.created_at.desc())
        )
        if not record:
            return None
        return self._domain(record)

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

    def expire_stale(self, *, user_id: UUID | None = None, kind: str | None = None) -> int:
        """Fail jobs that exceeded hard timeout or lost heartbeat."""
        statement = select(AiJobRecord).where(AiJobRecord.status.in_(ACTIVE_STATUSES))
        if user_id is not None:
            statement = statement.where(AiJobRecord.user_id == user_id)
        if kind is not None:
            statement = statement.where(AiJobRecord.kind == kind)
        expired = 0
        for record in self._session.scalars(statement).all():
            if self._expire_if_stale(record, commit=False):
                expired += 1
        if expired:
            self._session.commit()
        return expired

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
        self.expire_stale(kind=kind)
        stale_before = datetime.now(UTC) - STALE_HEARTBEAT
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
        # Too many recoveries means the worker keeps dying mid-job; fail instead of looping.
        if record.attempt_count >= 2 and record.status == "processing":
            self.fail(
                record,
                "后台任务多次中断后已停止，请缩小资料或降低题目数量后重新导入",
            )
            if self._session.bind is not None and self._session.bind.dialect.name == "postgresql":
                self._session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": 781204})
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

    def _expire_if_stale(self, record: AiJobRecord, *, commit: bool = True) -> bool:
        if record.status not in ACTIVE_STATUSES:
            return False
        now = datetime.now(UTC)
        created = record.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        heartbeat = record.heartbeat_at
        if heartbeat is not None and heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=UTC)
        soft_limit = max(record.estimated_seconds * 3, int(HARD_TIMEOUT.total_seconds()))
        timed_out = (now - created).total_seconds() > soft_limit
        heartbeat_stale = heartbeat is None or (now - heartbeat) > STALE_HEARTBEAT
        # queued: expire by absolute age only; processing: age or lost heartbeat.
        if record.status == "queued" and not timed_out:
            return False
        if record.status == "processing" and not timed_out and not heartbeat_stale:
            return False
        if not timed_out and not heartbeat_stale:
            return False
        reason = (
            "后台任务超时已自动停止，请缩小资料或降低题目数量后重试"
            if timed_out
            else "后台任务长时间无进度已自动停止，请重新导入"
        )
        record.status = "failed"
        record.stage = "处理失败"
        record.error = reason
        record.updated_at = now
        record.completed_at = now
        if commit:
            self._session.commit()
        return True

    @staticmethod
    def _domain(record: AiJobRecord) -> AiJobStatus:
        return AiJobStatus.model_validate(record, from_attributes=True)

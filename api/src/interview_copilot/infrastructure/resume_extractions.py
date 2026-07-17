from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from interview_copilot.domain.resume import ResumeExtractionResult
from interview_copilot.infrastructure.database import Base
from interview_copilot.infrastructure.questions import json_type


class ResumeExtractionCacheRecord(Base):
    __tablename__ = "resume_extraction_cache"
    __table_args__ = (
        UniqueConstraint("user_id", "fingerprint", name="uq_resume_cache_user_fingerprint"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    fingerprint: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(json_type)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlAlchemyResumeExtractionCache:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, user_id: UUID, fingerprint: str) -> ResumeExtractionResult | None:
        record = self._session.scalar(
            select(ResumeExtractionCacheRecord).where(
                ResumeExtractionCacheRecord.user_id == user_id,
                ResumeExtractionCacheRecord.fingerprint == fingerprint,
            )
        )
        return ResumeExtractionResult.model_validate(record.result) if record else None

    def put(
        self,
        *,
        user_id: UUID,
        fingerprint: str,
        result: ResumeExtractionResult,
    ) -> None:
        now = datetime.now(UTC)
        record = self._session.scalar(
            select(ResumeExtractionCacheRecord).where(
                ResumeExtractionCacheRecord.user_id == user_id,
                ResumeExtractionCacheRecord.fingerprint == fingerprint,
            )
        )
        if record:
            record.result = result.model_dump(mode="json")
            record.updated_at = now
        else:
            self._session.add(
                ResumeExtractionCacheRecord(
                    user_id=user_id,
                    fingerprint=fingerprint,
                    result=result.model_dump(mode="json"),
                    created_at=now,
                    updated_at=now,
                )
            )
        self._session.commit()

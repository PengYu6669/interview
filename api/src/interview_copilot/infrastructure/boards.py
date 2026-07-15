from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from interview_copilot.infrastructure.database import Base

json_type = JSON().with_variant(JSONB, "postgresql")


class InterviewBoardSnapshotRecord(Base):
    __tablename__ = "interview_board_snapshots"
    __table_args__ = (
        UniqueConstraint("session_id", "revision"),
        UniqueConstraint("user_id", "client_snapshot_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer)
    client_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    state: Mapped[dict] = mapped_column(json_type)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

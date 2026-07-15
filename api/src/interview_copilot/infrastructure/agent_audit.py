import asyncio
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from interview_copilot.application.agent.tools import ToolAuditEvent
from interview_copilot.infrastructure.database import Base, SessionFactory
from interview_copilot.infrastructure.questions import json_type


class AgentToolAuditRecord(Base):
    __tablename__ = "agent_tool_audits"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[UUID] = mapped_column(index=True)
    session_id: Mapped[UUID | None] = mapped_column(index=True, nullable=True)
    tool_call_id: Mapped[str] = mapped_column(String(200))
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    argument_summary: Mapped[dict[str, object]] = mapped_column(json_type)
    succeeded: Mapped[bool] = mapped_column(Boolean)
    duration_ms: Mapped[int] = mapped_column(Integer)
    error_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SqlAlchemyToolAuditSink:
    async def record(self, event: ToolAuditEvent) -> None:
        await asyncio.to_thread(self._record_sync, event)

    @staticmethod
    def _record_sync(event: ToolAuditEvent) -> None:
        with SessionFactory() as session:
            session.add(
                AgentToolAuditRecord(
                    user_id=event.user_id,
                    request_id=event.request_id,
                    session_id=event.session_id,
                    tool_call_id=event.tool_call_id,
                    tool_name=event.tool_name,
                    argument_summary=event.argument_summary,
                    succeeded=event.succeeded,
                    duration_ms=event.duration_ms,
                    error_type=event.error_type,
                    created_at=event.created_at,
                )
            )
            session.commit()

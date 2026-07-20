from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from interview_copilot.domain.admin import AdminSystemLog, AdminUserSummary
from interview_copilot.infrastructure.agent_audit import AgentToolAuditRecord
from interview_copilot.infrastructure.database import UserRecord


class AdminManagementService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_users(self, *, query: str = "", limit: int = 100) -> list[AdminUserSummary]:
        statement: Select[tuple[UserRecord]] = select(UserRecord).order_by(
            UserRecord.created_at.desc()
        )
        normalized = query.strip()
        if normalized:
            pattern = f"%{normalized}%"
            statement = statement.where(
                UserRecord.username.ilike(pattern) | UserRecord.email.ilike(pattern)
            )
        records = self._session.scalars(statement.limit(limit)).all()
        return [AdminUserSummary.model_validate(record) for record in records]

    def list_logs(self, *, limit: int = 100) -> list[AdminSystemLog]:
        records = self._session.scalars(
            select(AgentToolAuditRecord)
            .order_by(AgentToolAuditRecord.created_at.desc())
            .limit(limit)
        ).all()
        return [
            AdminSystemLog(
                id=record.id,
                request_id=record.request_id,
                session_id=record.session_id,
                tool_name=record.tool_name,
                succeeded=record.succeeded,
                duration_ms=record.duration_ms,
                error_type=record.error_type,
                created_at=record.created_at,
            )
            for record in records
        ]

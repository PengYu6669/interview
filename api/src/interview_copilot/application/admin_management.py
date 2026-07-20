from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.orm import Session

from interview_copilot.domain.admin import (
    AdminSystemLog,
    AdminUserList,
    AdminUserMetrics,
    AdminUserSummary,
)
from interview_copilot.infrastructure.agent_audit import AgentToolAuditRecord
from interview_copilot.infrastructure.database import AuthSessionRecord, UserRecord

_ADMIN_TIMEZONE = ZoneInfo("Asia/Shanghai")


class AdminManagementService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_users(self, *, query: str = "", limit: int = 100) -> AdminUserList:
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
        return AdminUserList(
            metrics=self._user_metrics(),
            users=[AdminUserSummary.model_validate(record) for record in records],
        )

    def _user_metrics(self) -> AdminUserMetrics:
        now = datetime.now(UTC)
        local_today = now.astimezone(_ADMIN_TIMEZONE).date()
        today_start = datetime.combine(local_today, time.min, _ADMIN_TIMEZONE).astimezone(UTC)
        week_start = today_start - timedelta(days=6)
        counts = self._session.execute(
            select(
                func.count(UserRecord.id),
                func.count(UserRecord.id).filter(UserRecord.created_at >= today_start),
                func.count(UserRecord.id).filter(UserRecord.role == "admin"),
            )
        ).one()
        daily_active = self._session.scalar(
            select(func.count(distinct(AuthSessionRecord.user_id))).where(
                AuthSessionRecord.last_active_at >= today_start
            )
        )
        weekly_active = self._session.scalar(
            select(func.count(distinct(AuthSessionRecord.user_id))).where(
                AuthSessionRecord.last_active_at >= week_start
            )
        )
        return AdminUserMetrics(
            total_users=counts[0],
            new_users_today=counts[1],
            admin_users=counts[2],
            daily_active_users=daily_active or 0,
            weekly_active_users=weekly_active or 0,
        )

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

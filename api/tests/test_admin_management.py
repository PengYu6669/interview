from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.admin_management import AdminManagementService
from interview_copilot.infrastructure.database import AuthSessionRecord, Base, UserRecord


def test_user_metrics_count_distinct_active_users() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session:
        admin = UserRecord(
            username="admin",
            email="admin@example.com",
            password_hash="hash",
            role="admin",
            created_at=now,
        )
        active = UserRecord(
            username="active",
            email="active@example.com",
            password_hash="hash",
            role="user",
            created_at=now - timedelta(days=30),
        )
        weekly = UserRecord(
            username="weekly",
            email="weekly@example.com",
            password_hash="hash",
            role="user",
            created_at=now - timedelta(days=30),
        )
        session.add_all([admin, active, weekly])
        session.flush()
        session.add_all(
            [
                AuthSessionRecord(
                    user_id=admin.id,
                    token_hash="a" * 64,
                    created_at=now,
                    last_active_at=now,
                    expires_at=now + timedelta(days=1),
                ),
                AuthSessionRecord(
                    user_id=admin.id,
                    token_hash="b" * 64,
                    created_at=now,
                    last_active_at=now,
                    expires_at=now + timedelta(days=1),
                ),
                AuthSessionRecord(
                    user_id=active.id,
                    token_hash="c" * 64,
                    created_at=now,
                    last_active_at=now,
                    expires_at=now + timedelta(days=1),
                ),
                AuthSessionRecord(
                    user_id=weekly.id,
                    token_hash="d" * 64,
                    created_at=now,
                    last_active_at=now - timedelta(days=2),
                    expires_at=now + timedelta(days=1),
                ),
            ]
        )
        session.commit()

        result = AdminManagementService(session).list_users()

    assert result.metrics.total_users == 3
    assert result.metrics.daily_active_users == 2
    assert result.metrics.weekly_active_users == 3
    assert result.metrics.new_users_today == 1
    assert result.metrics.admin_users == 1
    assert len(result.users) == 3

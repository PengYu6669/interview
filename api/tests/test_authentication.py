from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from interview_copilot.api.auth import LoginRequest
from interview_copilot.api.auth import login as login_endpoint
from interview_copilot.application.authentication import (
    AuthenticationService,
    DuplicateAccountError,
    InvalidCredentialsError,
    InvalidSessionError,
    LoginRateLimitExceeded,
)
from interview_copilot.infrastructure.database import AuthSessionRecord, Base


@pytest.fixture
def database() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def service(database: Session) -> AuthenticationService:
    return AuthenticationService(database, session_days=7)


def test_register_login_authenticate_and_logout(service: AuthenticationService) -> None:
    registered = service.register(username="测试用户", email="USER@example.com", password="123456")

    assert registered.user.username == "测试用户"
    assert registered.user.email == "user@example.com"
    assert service.authenticate(registered.session_token).id == registered.user.id

    logged_in = service.login(identifier="USER@EXAMPLE.COM", password="123456")
    assert logged_in.user.id == registered.user.id

    service.logout(logged_in.session_token)
    with pytest.raises(InvalidSessionError):
        service.authenticate(logged_in.session_token)


def test_rejects_duplicate_account(service: AuthenticationService) -> None:
    service.register(username="first_user", email="first@example.com", password="password-123")

    with pytest.raises(DuplicateAccountError):
        service.register(
            username="FIRST_USER", email="another@example.com", password="password-123"
        )


def test_accepts_numeric_username_and_six_character_password(
    service: AuthenticationService,
) -> None:
    registered = service.register(username="123456", email="numeric@example.com", password="123456")

    assert registered.user.username == "123456"


def test_login_uses_a_generic_error_for_unknown_user_and_wrong_password(
    service: AuthenticationService,
) -> None:
    service.register(username="known_user", email="known@example.com", password="password-123")

    with pytest.raises(InvalidCredentialsError, match="账号或密码错误"):
        service.login(identifier="known_user", password="wrong-password")
    with pytest.raises(InvalidCredentialsError, match="账号或密码错误"):
        service.login(identifier="missing_user", password="wrong-password")


def test_new_login_removes_expired_and_revoked_sessions(
    service: AuthenticationService,
    database: Session,
) -> None:
    registered = service.register(
        username="session_owner",
        email="session-owner@example.com",
        password="123456",
    )
    user_id = registered.user.id
    now = datetime.now(UTC)
    database.add_all(
        [
            AuthSessionRecord(
                user_id=user_id,
                token_hash="a" * 64,
                created_at=now - timedelta(days=10),
                expires_at=now - timedelta(days=1),
            ),
            AuthSessionRecord(
                user_id=user_id,
                token_hash="b" * 64,
                created_at=now,
                expires_at=now + timedelta(days=1),
                revoked_at=now,
            ),
        ]
    )
    database.commit()

    service.login(identifier="session_owner", password="123456")

    records = database.scalars(
        select(AuthSessionRecord).where(AuthSessionRecord.user_id == user_id)
    ).all()
    assert len(records) == 2
    assert {record.token_hash for record in records}.isdisjoint({"a" * 64, "b" * 64})
    assert all(record.revoked_at is None for record in records)


def test_login_rate_limit_blocks_and_clears_without_revealing_account_state(
    database: Session,
) -> None:
    class FakeLimiter:
        retry_seconds: int | None = None
        failure_retry_seconds: int | None = None
        cleared: list[str] = []

        def retry_after(self, identifier: str) -> int | None:
            assert identifier == "limited_user"
            return self.retry_seconds

        def record_failure(self, identifier: str) -> int | None:
            assert identifier == "limited_user"
            return self.failure_retry_seconds

        def clear(self, identifier: str) -> None:
            self.cleared.append(identifier)

    setup = AuthenticationService(database, session_days=7)
    setup.register(
        username="limited_user",
        email="limited-user@example.com",
        password="123456",
    )
    limiter = FakeLimiter()
    service = AuthenticationService(database, session_days=7, login_limiter=limiter)

    limiter.retry_seconds = 90
    with pytest.raises(LoginRateLimitExceeded) as blocked:
        service.login(identifier="LIMITED_USER", password="123456")
    assert blocked.value.retry_after_seconds == 90

    limiter.retry_seconds = None
    limiter.failure_retry_seconds = 75
    with pytest.raises(LoginRateLimitExceeded) as triggered:
        service.login(identifier="LIMITED_USER", password="wrong-password")
    assert triggered.value.retry_after_seconds == 75

    limiter.failure_retry_seconds = None
    result = service.login(identifier="LIMITED_USER", password="123456")
    assert result.user.username == "limited_user"
    assert limiter.cleared == ["limited_user"]


def test_login_endpoint_returns_retry_after_for_rate_limit(database: Session) -> None:
    class BlockedLimiter:
        def retry_after(self, identifier: str) -> int | None:
            return 42

        def record_failure(self, identifier: str) -> int | None:
            return 42

        def clear(self, identifier: str) -> None:
            raise AssertionError("受限请求不能清除计数")

    service = AuthenticationService(
        database,
        session_days=7,
        login_limiter=BlockedLimiter(),
    )

    with pytest.raises(HTTPException) as response:
        login_endpoint(
            LoginRequest(identifier="unknown", password="wrong-password"),
            service,
        )

    assert response.value.status_code == 429
    assert response.value.detail == "登录尝试过于频繁，请稍后再试"
    assert response.value.headers == {"Retry-After": "42"}


@pytest.mark.parametrize(
    ("username", "email", "password", "message"),
    [
        ("ab", "valid@example.com", "password-123", "用户名"),
        ("valid_user", "invalid", "password-123", "邮箱"),
        ("valid_user", "valid@example.com", "12345", "至少需要"),
    ],
)
def test_rejects_invalid_registration_fields(
    service: AuthenticationService,
    username: str,
    email: str,
    password: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        service.register(username=username, email=email, password=password)

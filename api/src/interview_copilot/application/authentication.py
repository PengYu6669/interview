import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from interview_copilot.domain.auth import AuthResult, UserProfile
from interview_copilot.infrastructure.database import AuthSessionRecord, UserRecord

USERNAME_PATTERN = re.compile(r"^\w{3,50}$", re.UNICODE)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_MIN_LENGTH = 6
PASSWORD_MAX_BYTES = 128
_PASSWORD_HASHER = PasswordHasher()
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("not-a-real-user-password")


class DuplicateAccountError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InvalidSessionError(ValueError):
    pass


class LoginRateLimitExceeded(ValueError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("登录尝试过于频繁，请稍后再试")
        self.retry_after_seconds = retry_after_seconds


class LoginAttemptLimiter(Protocol):
    def retry_after(self, identifier: str) -> int | None: ...

    def record_failure(self, identifier: str) -> int | None: ...

    def clear(self, identifier: str) -> None: ...


class AuthenticationService:
    def __init__(
        self,
        session: Session,
        *,
        session_days: int,
        login_limiter: LoginAttemptLimiter | None = None,
    ) -> None:
        self._session = session
        self._session_duration = timedelta(days=session_days)
        self._passwords = _PASSWORD_HASHER
        self._login_limiter = login_limiter

    def register(self, *, username: str, email: str, password: str) -> AuthResult:
        normalized_username = username.strip().lower()
        normalized_email = email.strip().lower()
        self._validate_registration(normalized_username, normalized_email, password)

        existing = self._session.scalar(
            select(UserRecord).where(
                or_(
                    UserRecord.username == normalized_username,
                    UserRecord.email == normalized_email,
                )
            )
        )
        if existing:
            raise DuplicateAccountError("用户名或邮箱已被使用")

        now = datetime.now(UTC)
        user = UserRecord(
            username=normalized_username,
            email=normalized_email,
            password_hash=self._passwords.hash(password),
            created_at=now,
        )
        self._session.add(user)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise DuplicateAccountError("用户名或邮箱已被使用") from exc
        result = self._create_session(user, now=now)
        self._session.commit()
        return result

    def login(self, *, identifier: str, password: str) -> AuthResult:
        normalized = identifier.strip().lower()
        retry_after = self._login_limiter.retry_after(normalized) if self._login_limiter else None
        if retry_after is not None:
            raise LoginRateLimitExceeded(retry_after)
        user = self._session.scalar(
            select(UserRecord).where(
                or_(UserRecord.username == normalized, UserRecord.email == normalized)
            )
        )
        password_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
        verified: bool
        try:
            verified = bool(self._passwords.verify(password_hash, password))
        except (VerifyMismatchError, InvalidHashError):
            verified = False
        if not user or not verified:
            retry_after = (
                self._login_limiter.record_failure(normalized)
                if self._login_limiter
                else None
            )
            if retry_after is not None:
                raise LoginRateLimitExceeded(retry_after)
            raise InvalidCredentialsError("账号或密码错误")

        now = datetime.now(UTC)
        if self._login_limiter:
            self._login_limiter.clear(normalized)
        if self._passwords.check_needs_rehash(user.password_hash):
            user.password_hash = self._passwords.hash(password)
        result = self._create_session(user, now=now)
        self._session.commit()
        return result

    def authenticate(self, token: str) -> UserProfile:
        now = datetime.now(UTC)
        record = self._session.scalar(
            select(AuthSessionRecord).where(
                AuthSessionRecord.token_hash == self._hash_token(token),
                AuthSessionRecord.revoked_at.is_(None),
                AuthSessionRecord.expires_at > now,
            )
        )
        if not record:
            raise InvalidSessionError("登录状态已失效，请重新登录")
        return UserProfile.model_validate(record.user)

    def logout(self, token: str) -> None:
        record = self._session.scalar(
            select(AuthSessionRecord).where(
                AuthSessionRecord.token_hash == self._hash_token(token),
                AuthSessionRecord.revoked_at.is_(None),
            )
        )
        if record:
            record.revoked_at = datetime.now(UTC)
            self._session.commit()

    def _create_session(self, user: UserRecord, *, now: datetime) -> AuthResult:
        self._session.execute(
            delete(AuthSessionRecord).where(
                AuthSessionRecord.user_id == user.id,
                or_(
                    AuthSessionRecord.expires_at <= now,
                    AuthSessionRecord.revoked_at.is_not(None),
                ),
            )
        )
        token = secrets.token_urlsafe(32)
        expires_at = now + self._session_duration
        self._session.add(
            AuthSessionRecord(
                user=user,
                token_hash=self._hash_token(token),
                created_at=now,
                expires_at=expires_at,
            )
        )
        return AuthResult(
            user=UserProfile.model_validate(user),
            session_token=token,
            expires_at=expires_at,
        )

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _validate_registration(username: str, email: str, password: str) -> None:
        if not username:
            raise ValueError("请输入用户名")
        if not USERNAME_PATTERN.fullmatch(username):
            raise ValueError("用户名只能包含文字、字母、数字和下划线，长度为 3 至 50 位")
        if not EMAIL_PATTERN.fullmatch(email) or len(email) > 320:
            raise ValueError("邮箱格式不正确")
        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValueError(f"密码至少需要 {PASSWORD_MIN_LENGTH} 位")
        if len(password.encode()) > PASSWORD_MAX_BYTES:
            raise ValueError("密码过长")

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from interview_copilot.application.account_data import (
    AccountDataService,
    AccountNotFoundError,
    CurrentPasswordError,
)
from interview_copilot.application.authentication import (
    AuthenticationService,
    DuplicateAccountError,
    InvalidCredentialsError,
    InvalidSessionError,
    LoginRateLimitExceeded,
)
from interview_copilot.config import get_settings
from interview_copilot.domain.account import AccountDataExport, AccountDataSummary
from interview_copilot.domain.auth import AuthResult, UserProfile
from interview_copilot.infrastructure.database import get_database_session
from interview_copilot.infrastructure.login_rate_limit import RedisLoginAttemptLimiter

router = APIRouter(prefix="/v1/auth", tags=["auth"])
settings = get_settings()
login_attempt_limiter = RedisLoginAttemptLimiter(
    settings.redis_url,
    max_failures=settings.auth_login_max_failures,
    window_seconds=settings.auth_login_window_seconds,
)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class SessionTokenRequest(BaseModel):
    session_token: str = Field(min_length=20, max_length=200)


class DeleteAccountRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)


def get_authentication_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AuthenticationService:
    return AuthenticationService(
        session,
        session_days=settings.auth_session_days,
        login_limiter=login_attempt_limiter,
    )


def get_account_data_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AccountDataService:
    return AccountDataService(session)


def require_current_user(
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> UserProfile:
    token = _bearer_token(authorization)
    try:
        return service.authenticate(token)
    except InvalidSessionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_admin(
    user: Annotated[UserProfile, Depends(require_current_user)],
) -> UserProfile:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def optional_current_user(
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> UserProfile | None:
    if not authorization:
        return None
    return require_current_user(service, authorization)


@router.post("/register", response_model=AuthResult, status_code=201)
def register(
    request: RegisterRequest,
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> AuthResult:
    try:
        return service.register(
            username=request.username, email=request.email, password=request.password
        )
    except DuplicateAccountError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/login", response_model=AuthResult)
def login(
    request: LoginRequest,
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> AuthResult:
    try:
        return service.login(identifier=request.identifier, password=request.password)
    except LoginRateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me", response_model=UserProfile)
def current_user(
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> UserProfile:
    return require_current_user(service, authorization)


@router.post("/logout", status_code=204)
def logout(
    request: SessionTokenRequest,
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> None:
    service.logout(request.session_token)


@router.get("/account", response_model=AccountDataSummary)
def account_summary(
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[AccountDataService, Depends(get_account_data_service)],
) -> AccountDataSummary:
    try:
        return service.summary(user_id=user.id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/account/export", response_model=AccountDataExport)
def export_account_data(
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[AccountDataService, Depends(get_account_data_service)],
) -> AccountDataExport:
    try:
        return service.export(user_id=user.id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/account", status_code=204)
def delete_account(
    request: DeleteAccountRequest,
    user: Annotated[UserProfile, Depends(require_current_user)],
    service: Annotated[AccountDataService, Depends(get_account_data_service)],
) -> None:
    try:
        service.delete_account(user_id=user.id, current_password=request.current_password)
    except CurrentPasswordError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少登录凭据")
    return authorization.removeprefix("Bearer ").strip()

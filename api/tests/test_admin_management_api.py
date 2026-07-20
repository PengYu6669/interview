from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from interview_copilot.api.admin_management import admin_management_service, router
from interview_copilot.api.auth import require_admin
from interview_copilot.domain.admin import AdminSystemLog, AdminUserSummary
from interview_copilot.domain.auth import UserProfile


def _admin() -> UserProfile:
    return UserProfile(
        id=uuid4(),
        username="admin",
        email="admin@example.com",
        role="admin",
        created_at=datetime.now(UTC),
    )


class FakeAdminManagementService:
    def list_users(self, **_: object) -> list[AdminUserSummary]:
        return [
            AdminUserSummary(
                id=uuid4(),
                username="dick",
                email="dick@example.com",
                role="user",
                created_at=datetime.now(UTC),
            )
        ]

    def list_logs(self, **_: object) -> list[AdminSystemLog]:
        return [
            AdminSystemLog(
                id=uuid4(),
                request_id=uuid4(),
                session_id=None,
                tool_name="retrieve_job_evidence",
                succeeded=True,
                duration_ms=42,
                error_type=None,
                created_at=datetime.now(UTC),
            )
        ]


def _client(*, status_code: int | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[admin_management_service] = FakeAdminManagementService
    if status_code is None:
        app.dependency_overrides[require_admin] = _admin
    else:
        def reject() -> None:
            raise HTTPException(status_code=status_code, detail="需要管理员权限")

        app.dependency_overrides[require_admin] = reject
    return TestClient(app)


def test_admin_management_lists_users_and_logs() -> None:
    client = _client()

    users = client.get("/v1/admin/users?query=dick")
    logs = client.get("/v1/admin/logs")

    assert users.status_code == 200
    assert users.json()[0]["username"] == "dick"
    assert logs.status_code == 200
    assert logs.json()[0]["tool_name"] == "retrieve_job_evidence"


def test_admin_management_preserves_authentication_status() -> None:
    for status_code in (401, 403):
        client = _client(status_code=status_code)
        assert client.get("/v1/admin/users").status_code == status_code
        assert client.get("/v1/admin/logs").status_code == status_code

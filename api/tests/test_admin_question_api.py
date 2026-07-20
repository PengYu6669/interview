from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from interview_copilot.api.admin_questions import admin_question_service, router
from interview_copilot.api.auth import require_admin
from interview_copilot.domain.auth import UserProfile
from interview_copilot.domain.questions import AdminQuestionDetail, AdminQuestionSummary


def _admin() -> UserProfile:
    return UserProfile(
        id=uuid4(),
        username="admin",
        email="admin@example.com",
        role="admin",
        created_at=datetime.now(UTC),
    )


def _summary() -> AdminQuestionSummary:
    return AdminQuestionSummary(
        id=uuid4(),
        slug="admin-question",
        title="事务隔离",
        prompt="解释事务隔离级别",
        difficulty="进阶",
        question_type="原理",
        topics=[],
        framework="technical",
        published=False,
        owner_user_id=uuid4(),
        evidence_count=0,
        created_at=datetime.now(UTC),
    )


class FakeAdminQuestionService:
    def __init__(self) -> None:
        self.question = _summary()

    def list_managed(self):  # type: ignore[no-untyped-def]
        return [self.question]

    def set_publication(
        self, *, admin_user_id, question_id, published  # type: ignore[no-untyped-def]
    ) -> AdminQuestionSummary:
        del admin_user_id, question_id
        return self.question.model_copy(update={"published": published})

    async def create_managed(self, *, admin_user_id, **data):  # type: ignore[no-untyped-def]
        del admin_user_id
        return AdminQuestionDetail(
            **self.question.model_dump(),
            intent=data["intent"],
            answer_outline=data["answer_outline"],
            common_mistakes=data["common_mistakes"],
            content_markdown=data["content_markdown"],
        )

    def delete_managed(self, *, question_id):  # type: ignore[no-untyped-def]
        del question_id


def _client(*, status_code: int | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    service = FakeAdminQuestionService()
    app.dependency_overrides[admin_question_service] = lambda: service
    if status_code is None:
        app.dependency_overrides[require_admin] = _admin
    else:
        def reject() -> None:
            raise HTTPException(status_code=status_code, detail="无权管理题库")

        app.dependency_overrides[require_admin] = reject
    return TestClient(app)


@pytest.mark.parametrize("status_code", [401, 403])
def test_admin_question_api_preserves_authentication_status(status_code: int) -> None:
    response = _client(status_code=status_code).get("/v1/admin/questions")

    assert response.status_code == status_code


def test_admin_question_api_allows_admin_and_validates_publication_body() -> None:
    client = _client()
    listed = client.get("/v1/admin/questions")

    assert listed.status_code == 200
    question_id = listed.json()[0]["id"]
    invalid = client.patch(
        f"/v1/admin/questions/{question_id}/publication",
        json={"published": True, "owner_user_id": str(uuid4())},
    )
    assert invalid.status_code == 422

    published = client.patch(
        f"/v1/admin/questions/{question_id}/publication",
        json={"published": True},
    )
    assert published.status_code == 200
    assert published.json()["published"] is True

    payload = {
        "title": "缓存击穿",
        "prompt": "请解释缓存击穿",
        "difficulty": "进阶",
        "question_type": "场景",
        "framework": "technical",
        "intent": "考察缓存治理",
        "answer_outline": ["说明问题", "给出方案"],
        "common_mistakes": ["忽略超时"],
        "topic_names": ["缓存"],
        "content_markdown": "## 回答要点",
    }
    created = client.post("/v1/admin/questions", json=payload)
    assert created.status_code == 201
    assert client.delete(f"/v1/admin/questions/{question_id}").status_code == 204

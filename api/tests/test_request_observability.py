import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from interview_copilot.infrastructure.request_observability import (
    RequestObservabilityMiddleware,
    http_exception_response,
    unexpected_exception_response,
    validation_exception_response,
)


def observed_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestObservabilityMiddleware)
    app.add_exception_handler(HTTPException, http_exception_response)
    app.add_exception_handler(RequestValidationError, validation_exception_response)
    app.add_exception_handler(Exception, unexpected_exception_response)
    return app


def test_request_id_is_propagated_and_log_excludes_sensitive_data(
    caplog,
) -> None:
    app = observed_app()

    @app.post("/echo")
    async def echo() -> dict[str, str]:
        return {"status": "ok"}

    caplog.set_level(logging.INFO, logger="interview_copilot.access")
    with TestClient(app) as client:
        response = client.post(
            "/echo?token=query-secret",
            headers={"X-Request-ID": "request-test-123"},
            json={"resume": "private-resume-content"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-test-123"
    payload = json.loads(caplog.records[-1].message)
    assert payload["request_id"] == "request-test-123"
    assert payload["path"] == "/echo"
    assert payload["status_code"] == 200
    assert "query-secret" not in caplog.text
    assert "private-resume-content" not in caplog.text


def test_invalid_request_id_is_replaced() -> None:
    app = observed_app()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "invalid request id"})

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32
    assert request_id.isalnum()


def test_validation_error_does_not_echo_sensitive_input() -> None:
    app = observed_app()

    class Payload(BaseModel):
        answer: str = Field(max_length=5)

    @app.post("/answers")
    async def answer(_: Payload) -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        response = client.post(
            "/answers",
            headers={"X-Request-ID": "validation-request"},
            json={"answer": "private interview answer"},
        )

    assert response.status_code == 422
    assert response.json()["request_id"] == "validation-request"
    assert response.json()["detail"] == "请求数据格式不正确"
    assert "private interview answer" not in response.text

import json
import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("interview_copilot.access")
REQUEST_ID_HEADER = b"x-request-id"
VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestObservabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = self._request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        started = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self._app(scope, receive, send_with_request_id)
        finally:
            duration_ms = round((perf_counter() - started) * 1000, 2)
            logger.info(
                json.dumps(
                    {
                        "event": "http_request_completed",
                        "request_id": request_id,
                        "method": scope.get("method", ""),
                        "path": scope.get("path", ""),
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
            )

    @staticmethod
    def _request_id(scope: Scope) -> str:
        raw_headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
        for name, value in raw_headers:
            if name.lower() != REQUEST_ID_HEADER:
                continue
            try:
                candidate = value.decode("ascii")
            except UnicodeDecodeError:
                break
            if VALID_REQUEST_ID.fullmatch(candidate):
                return candidate
            break
        return uuid4().hex


def http_exception_response(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        return unexpected_exception_response(request, exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request.state.request_id},
        headers=exc.headers,
    )


def validation_exception_response(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return unexpected_exception_response(request, exc)
    errors = [
        {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "detail": "请求数据格式不正确",
            "errors": errors,
            "request_id": request.state.request_id,
        },
    )


def unexpected_exception_response(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.state.request_id
    logger.error(
        json.dumps(
            {
                "event": "http_request_failed",
                "request_id": request_id,
                "exception_type": type(exc).__name__,
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务内部错误", "request_id": request_id},
    )

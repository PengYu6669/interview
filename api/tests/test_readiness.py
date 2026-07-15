import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from interview_copilot import main


class FakeConnection:
    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, _: object) -> None:
        return None


class ReadyEngine:
    def connect(self) -> FakeConnection:
        return FakeConnection()


class OfflineEngine:
    def connect(self) -> FakeConnection:
        raise SQLAlchemyError("database offline")


class ReadyRedis:
    @classmethod
    def from_url(cls, *_: object, **__: object) -> "ReadyRedis":
        return cls()

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_readiness_checks_database_and_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "engine", ReadyEngine())
    monkeypatch.setattr(main, "Redis", ReadyRedis)

    assert await main.readiness() == {"status": "ready"}


@pytest.mark.asyncio
async def test_readiness_returns_503_when_dependency_is_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "engine", OfflineEngine())

    with pytest.raises(HTTPException) as caught:
        await main.readiness()

    assert caught.value.status_code == 503
    assert caught.value.detail == "依赖服务尚未就绪"

import logging

from redis.exceptions import RedisError

from interview_copilot.infrastructure.login_rate_limit import RedisLoginAttemptLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.last_key = ""
        self.deleted: list[str] = []

    def get(self, key: str) -> str | None:
        value = self.values.get(key)
        return None if value is None else str(value)

    def eval(self, script: str, numkeys: int, key: str, window_seconds: int) -> int:
        assert "INCR" in script
        assert numkeys == 1
        assert window_seconds == 60
        self.last_key = key
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    def ttl(self, key: str) -> int:
        return 60 if key in self.values else -2

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.values.pop(key, None)


def test_redis_login_limiter_hashes_identifier_and_enforces_threshold() -> None:
    redis = FakeRedis()
    limiter = RedisLoginAttemptLimiter(
        "redis://unused",
        max_failures=3,
        window_seconds=60,
        client=redis,
    )

    assert limiter.record_failure("USER@example.com") is None
    assert limiter.record_failure("USER@example.com") is None
    assert limiter.record_failure("USER@example.com") == 60
    assert "USER@example.com" not in redis.last_key
    assert limiter.retry_after("USER@example.com") == 60

    limiter.clear("USER@example.com")
    assert limiter.retry_after("USER@example.com") is None
    assert redis.deleted


def test_redis_login_limiter_logs_fail_open_security_degradation(
    caplog,
) -> None:  # type: ignore[no-untyped-def]
    class UnavailableRedis(FakeRedis):
        def get(self, key: str) -> str | None:
            raise RedisError("offline")

        def eval(self, script: str, numkeys: int, key: str, window_seconds: int) -> int:
            raise RedisError("offline")

        def delete(self, key: str) -> None:
            raise RedisError("offline")

    limiter = RedisLoginAttemptLimiter(
        "redis://unused",
        max_failures=3,
        window_seconds=60,
        client=UnavailableRedis(),
    )

    with caplog.at_level(logging.WARNING):
        assert limiter.retry_after("user") is None
        assert limiter.record_failure("user") is None
        limiter.clear("user")

    assert len(caplog.records) == 3
    assert all(getattr(record, "security_degraded", False) for record in caplog.records)

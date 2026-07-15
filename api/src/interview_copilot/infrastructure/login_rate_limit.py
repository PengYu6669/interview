import hashlib
import logging
from typing import Protocol, cast

from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

_INCREMENT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RedisRateLimitClient(Protocol):
    def get(self, key: str) -> str | bytes | int | None: ...

    def eval(self, script: str, numkeys: int, *keys_and_args: str | int) -> object: ...

    def ttl(self, key: str) -> int: ...

    def delete(self, key: str) -> object: ...


class RedisLoginAttemptLimiter:
    def __init__(
        self,
        redis_url: str,
        *,
        max_failures: int,
        window_seconds: int,
        client: RedisRateLimitClient | None = None,
    ) -> None:
        if not 3 <= max_failures <= 100:
            raise ValueError("登录失败次数限制必须为 3 至 100")
        if not 60 <= window_seconds <= 86_400:
            raise ValueError("登录限流窗口必须为 60 至 86400 秒")
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._client = client or cast(
            RedisRateLimitClient,
            Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            ),
        )

    def retry_after(self, identifier: str) -> int | None:
        key = self._key(identifier)
        try:
            raw_count = self._client.get(key)
            if raw_count is None or int(raw_count) < self._max_failures:
                return None
            return self._remaining_seconds(key)
        except (RedisError, TypeError, ValueError):
            self._log_degraded("check")
            return None

    def record_failure(self, identifier: str) -> int | None:
        key = self._key(identifier)
        try:
            raw_count = self._client.eval(
                _INCREMENT_SCRIPT,
                1,
                key,
                self._window_seconds,
            )
            if not isinstance(raw_count, (str, bytes, int)):
                raise TypeError("Redis 登录限流计数响应无效")
            count = int(raw_count)
            if count < self._max_failures:
                return None
            return self._remaining_seconds(key)
        except (RedisError, TypeError, ValueError):
            self._log_degraded("record_failure")
            return None

    def clear(self, identifier: str) -> None:
        try:
            self._client.delete(self._key(identifier))
        except RedisError:
            self._log_degraded("clear")

    def _remaining_seconds(self, key: str) -> int:
        ttl = int(self._client.ttl(key))
        return ttl if ttl > 0 else self._window_seconds

    @staticmethod
    def _key(identifier: str) -> str:
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return f"auth:login-failures:{digest}"

    @staticmethod
    def _log_degraded(operation: str) -> None:
        logger.warning(
            "登录限流 Redis 不可用，当前请求按可用性策略继续",
            extra={"operation": operation, "security_degraded": True},
        )

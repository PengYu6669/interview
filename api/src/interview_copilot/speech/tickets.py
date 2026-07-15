import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Protocol
from uuid import UUID

from redis.exceptions import RedisError


class InvalidSpeechTicketError(ValueError):
    pass


class SpeechTicketStoreError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SpeechTicketData:
    user_id: UUID
    session_id: UUID
    expires_at: datetime
    nonce: str


class AsyncTicketStore(Protocol):
    async def set(
        self,
        name: str,
        value: str,
        *,
        ex: int,
        nx: bool,
    ) -> object: ...


class SpeechTicketReplayGuard:
    def __init__(self, store: AsyncTicketStore) -> None:
        self._store = store

    async def consume(self, ticket: SpeechTicketData) -> None:
        ttl = max(1, ceil((ticket.expires_at - datetime.now(UTC)).total_seconds()))
        nonce_hash = hashlib.sha256(ticket.nonce.encode("utf-8")).hexdigest()
        try:
            accepted = await self._store.set(
                f"speech:ticket:{nonce_hash}",
                "1",
                ex=ttl,
                nx=True,
            )
        except RedisError as exc:
            raise SpeechTicketStoreError("语音票据消费服务暂时不可用") from exc
        if not accepted:
            raise InvalidSpeechTicketError("语音票据已使用")


class SpeechTicketSigner:
    def __init__(self, secret: str, *, lifetime_seconds: int = 90) -> None:
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("语音票据密钥至少需要 32 字节")
        self._secret = secret.encode("utf-8")
        self._lifetime = timedelta(seconds=lifetime_seconds)

    def issue(self, *, user_id: UUID, session_id: UUID) -> tuple[str, datetime]:
        expires_at = datetime.now(UTC) + self._lifetime
        payload = {
            "user_id": str(user_id),
            "session_id": str(session_id),
            "expires_at": int(expires_at.timestamp()),
            "nonce": secrets.token_urlsafe(12),
        }
        encoded = self._encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = self._encode(hmac.new(self._secret, encoded, hashlib.sha256).digest())
        return f"{encoded.decode('ascii')}.{signature.decode('ascii')}", expires_at

    def verify(self, ticket: str) -> SpeechTicketData:
        try:
            encoded_text, signature_text = ticket.split(".", 1)
            encoded = encoded_text.encode("ascii")
            supplied = self._decode(signature_text)
            expected = hmac.new(self._secret, encoded, hashlib.sha256).digest()
            if not hmac.compare_digest(supplied, expected):
                raise InvalidSpeechTicketError("语音票据签名无效")
            payload = json.loads(self._decode(encoded_text))
            expires_at = datetime.fromtimestamp(int(payload["expires_at"]), tz=UTC)
            if expires_at <= datetime.now(UTC):
                raise InvalidSpeechTicketError("语音票据已过期")
            return SpeechTicketData(
                user_id=UUID(payload["user_id"]),
                session_id=UUID(payload["session_id"]),
                expires_at=expires_at,
                nonce=str(payload["nonce"]),
            )
        except InvalidSpeechTicketError:
            raise
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise InvalidSpeechTicketError("语音票据格式无效") from exc

    @staticmethod
    def _encode(value: bytes) -> bytes:
        return base64.urlsafe_b64encode(value).rstrip(b"=")

    @staticmethod
    def _decode(value: str) -> bytes:
        raw = value.encode("ascii")
        return base64.urlsafe_b64decode(raw + b"=" * (-len(raw) % 4))

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from redis.exceptions import RedisError

from interview_copilot.speech.tickets import (
    InvalidSpeechTicketError,
    SpeechTicketReplayGuard,
    SpeechTicketSigner,
    SpeechTicketStoreError,
)
from interview_copilot.speech.xfyun_iat import XfyunIAT


def test_speech_ticket_round_trip_and_session_binding() -> None:
    user_id = uuid4()
    session_id = uuid4()
    signer = SpeechTicketSigner("x" * 32)

    ticket, expires_at = signer.issue(user_id=user_id, session_id=session_id)
    payload = signer.verify(ticket)

    assert payload.user_id == user_id
    assert payload.session_id == session_id
    assert payload.expires_at <= expires_at
    assert payload.expires_at > datetime.now(UTC)


def test_speech_ticket_rejects_tampering() -> None:
    signer = SpeechTicketSigner("x" * 32)
    ticket, _ = signer.issue(user_id=uuid4(), session_id=uuid4())
    encoded, signature = ticket.split(".", 1)
    position = len(signature) // 2
    replacement = "A" if signature[position] != "A" else "B"
    tampered = f"{signature[:position]}{replacement}{signature[position + 1 :]}"

    with pytest.raises(InvalidSpeechTicketError, match="签名无效"):
        signer.verify(f"{encoded}.{tampered}")


def test_speech_ticket_rejects_expired_ticket() -> None:
    signer = SpeechTicketSigner("x" * 32, lifetime_seconds=-1)
    ticket, _ = signer.issue(user_id=uuid4(), session_id=uuid4())

    with pytest.raises(InvalidSpeechTicketError, match="已过期"):
        signer.verify(ticket)


class FakeTicketStore:
    def __init__(self, *, fail: bool = False) -> None:
        self.keys: set[str] = set()
        self.fail = fail

    async def set(self, name: str, value: str, *, ex: int, nx: bool) -> bool:
        del value, ex, nx
        if self.fail:
            raise RedisError("offline")
        if name in self.keys:
            return False
        self.keys.add(name)
        return True


@pytest.mark.asyncio
async def test_speech_ticket_is_consumed_only_once() -> None:
    signer = SpeechTicketSigner("x" * 32)
    ticket, _ = signer.issue(user_id=uuid4(), session_id=uuid4())
    payload = signer.verify(ticket)
    guard = SpeechTicketReplayGuard(FakeTicketStore())

    await guard.consume(payload)
    with pytest.raises(InvalidSpeechTicketError, match="已使用"):
        await guard.consume(payload)


@pytest.mark.asyncio
async def test_speech_ticket_consumption_fails_closed_when_store_is_offline() -> None:
    signer = SpeechTicketSigner("x" * 32)
    ticket, _ = signer.issue(user_id=uuid4(), session_id=uuid4())
    payload = signer.verify(ticket)

    with pytest.raises(SpeechTicketStoreError, match="暂时不可用"):
        await SpeechTicketReplayGuard(FakeTicketStore(fail=True)).consume(payload)


def test_xfyun_iat_merges_dynamic_correction() -> None:
    transcripts: dict[int, str] = {}
    XfyunIAT._merge_result(
        transcripts,
        {"sn": 0, "ws": [{"cw": [{"w": "我使用"}]}]},
    )
    XfyunIAT._merge_result(
        transcripts,
        {"sn": 1, "ws": [{"cw": [{"w": "Python。"}]}]},
    )
    XfyunIAT._merge_result(
        transcripts,
        {
            "sn": 2,
            "pgs": "rpl",
            "rg": [0, 1],
            "ws": [{"cw": [{"w": "我主要使用 Python。"}]}],
        },
    )

    assert "".join(transcripts[index] for index in sorted(transcripts)) == ("我主要使用 Python。")

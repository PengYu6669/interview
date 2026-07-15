from uuid import uuid4

import pytest

from interview_copilot.application.claim_verification import (
    ClaimVerificationError,
    InterviewClaimVerificationService,
)
from interview_copilot.domain.interviews import (
    ClaimVerificationDecision,
    VerifiableClaim,
)
from interview_copilot.domain.retrieval import RetrievedEvidence


class FakeSearch:
    def __init__(self, evidence: list[RetrievedEvidence]) -> None:
        self.evidence = evidence
        self.calls: list[dict[str, object]] = []

    async def search(self, **kwargs: object) -> list[RetrievedEvidence]:
        self.calls.append(kwargs)
        return self.evidence


class FakeProvider:
    model_name = "fake-verifier"
    prompt_version = "claim-verification-test-v1"

    def __init__(
        self,
        *,
        claims: list[VerifiableClaim],
        decisions: list[ClaimVerificationDecision],
    ) -> None:
        self.claims = claims
        self.decisions = decisions
        self.verify_calls = 0

    async def extract_claims(self, **_: object) -> list[VerifiableClaim]:
        return self.claims

    async def verify_claims(self, **_: object) -> list[ClaimVerificationDecision]:
        self.verify_calls += 1
        return self.decisions


def _claim(quote: str = "RRF 不需要统一两路分值") -> VerifiableClaim:
    return VerifiableClaim(
        sequence=1,
        claim="RRF 融合不要求稠密与词法召回分值处于同一量尺",
        evidence_quote=quote,
    )


def _evidence() -> RetrievedEvidence:
    return RetrievedEvidence(
        chunk_id=uuid4(),
        document_id=uuid4(),
        corpus_type="knowledge",
        source_type="curated_knowledge_pack",
        title="AI 应用开发面试知识包",
        content="RRF 可以融合不同分值尺度的候选排名。",
        heading_path=["混合召回、阈值与重排"],
        page_start=None,
        page_end=None,
        source_metadata={
            "version": "1.0.0",
            "sources": [{"url": "https://www.postgresql.org/docs/current/textsearch.html"}],
        },
        score=0.8,
        matched_by=["dense", "lexical"],
    )


@pytest.mark.asyncio
async def test_verifies_claim_with_curated_citation() -> None:
    search = FakeSearch([_evidence()])
    provider = FakeProvider(
        claims=[_claim()],
        decisions=[
            ClaimVerificationDecision(
                claim_index=0,
                result="supported",
                confidence=0.9,
                rationale="知识证据直接支持该主张。",
                citation_indexes=[1],
            )
        ],
    )
    service = InterviewClaimVerificationService(search, provider)  # type: ignore[arg-type]

    result = await service.verify(
        user_id=uuid4(),
        turns=[{"sequence": 1, "answer": "RRF 不需要统一两路分值。"}],
    )

    assert result[0].result == "supported"
    assert result[0].citations[0].version == "1.0.0"
    assert result[0].citations[0].source_urls == [
        "https://www.postgresql.org/docs/current/textsearch.html"
    ]
    assert search.calls[0]["source_types"] == ["curated_knowledge_pack"]


@pytest.mark.asyncio
async def test_no_evidence_is_uncertain_without_verifier_call() -> None:
    provider = FakeProvider(claims=[_claim()], decisions=[])
    service = InterviewClaimVerificationService(  # type: ignore[arg-type]
        FakeSearch([]),
        provider,
    )

    result = await service.verify(
        user_id=uuid4(),
        turns=[{"sequence": 1, "answer": "RRF 不需要统一两路分值。"}],
    )

    assert result[0].result == "uncertain"
    assert result[0].confidence == 0
    assert result[0].citations == []
    assert provider.verify_calls == 0


@pytest.mark.asyncio
async def test_rejects_fabricated_quote_and_downgrades_weak_contradiction() -> None:
    fabricated = InterviewClaimVerificationService(  # type: ignore[arg-type]
        FakeSearch([_evidence()]),
        FakeProvider(claims=[_claim("并不存在的原话")], decisions=[]),
    )
    with pytest.raises(ClaimVerificationError, match="回答原话"):
        await fabricated.verify(
            user_id=uuid4(),
            turns=[{"sequence": 1, "answer": "RRF 不需要统一两路分值。"}],
        )

    weak = InterviewClaimVerificationService(  # type: ignore[arg-type]
        FakeSearch([_evidence()]),
        FakeProvider(
            claims=[_claim()],
            decisions=[
                ClaimVerificationDecision(
                    claim_index=0,
                    result="contradicted",
                    confidence=0.7,
                    rationale="存在一些冲突。",
                    citation_indexes=[1],
                )
            ],
        ),
    )
    result = await weak.verify(
        user_id=uuid4(),
        turns=[{"sequence": 1, "answer": "RRF 不需要统一两路分值。"}],
    )

    assert result[0].result == "uncertain"
    assert "不能把该主张定性" in result[0].rationale

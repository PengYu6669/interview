from typing import Protocol
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from interview_copilot.application.retrieval.search import RagSearchService
from interview_copilot.domain.interviews import (
    ClaimVerificationDecision,
    VerifiableClaim,
    VerificationCitation,
    VerifiedClaim,
)
from interview_copilot.domain.retrieval import RetrievedEvidence
from interview_copilot.providers.dashscope_embedding import DashScopeError


class ClaimVerificationError(RuntimeError):
    pass


class ClaimVerificationProvider(Protocol):
    model_name: str
    prompt_version: str

    async def extract_claims(
        self,
        *,
        turns: list[dict[str, object]],
    ) -> list[VerifiableClaim]: ...

    async def verify_claims(
        self,
        *,
        items: list[dict[str, object]],
    ) -> list[ClaimVerificationDecision]: ...


class InterviewClaimVerificationService:
    def __init__(
        self,
        search: RagSearchService,
        provider: ClaimVerificationProvider,
    ) -> None:
        self._search = search
        self._provider = provider

    async def verify(
        self,
        *,
        user_id: UUID,
        turns: list[dict[str, object]],
    ) -> list[VerifiedClaim]:
        claims = await self._provider.extract_claims(turns=turns)
        if not claims:
            return []
        answers: dict[int, str] = {}
        for turn in turns:
            sequence = turn.get("sequence")
            answer = turn.get("answer")
            if isinstance(sequence, int) and isinstance(answer, str):
                answers[sequence] = answer
        for claim in claims:
            source = answers.get(claim.sequence)
            if not source or claim.evidence_quote not in source:
                raise ClaimVerificationError("主张提取结果引用了不存在的回答原话")

        evidence_by_claim: dict[int, list[RetrievedEvidence]] = {}
        verification_items: list[dict[str, object]] = []
        for index, claim in enumerate(claims):
            try:
                evidence = await self._search.search(
                    user_id=user_id,
                    query=claim.claim,
                    corpus_types=["knowledge"],
                    source_types=["curated_knowledge_pack"],
                    limit=5,
                )
            except (DashScopeError, SQLAlchemyError) as exc:
                raise ClaimVerificationError("权威知识检索暂时不可用") from exc
            evidence_by_claim[index] = evidence
            if evidence:
                verification_items.append(
                    {
                        "claim_index": index,
                        "claim": claim.model_dump(mode="json"),
                        "evidence": [
                            {
                                "citation_index": evidence_index,
                                "title": item.title,
                                "content": item.content[:1_500],
                                "version": item.source_metadata.get("version"),
                            }
                            for evidence_index, item in enumerate(evidence, 1)
                        ],
                    }
                )

        decisions = (
            await self._provider.verify_claims(items=verification_items)
            if verification_items
            else []
        )
        decisions_by_claim = {item.claim_index: item for item in decisions}
        results: list[VerifiedClaim] = []
        for index, claim in enumerate(claims):
            evidence = evidence_by_claim[index]
            decision = decisions_by_claim.get(index)
            if not evidence:
                results.append(
                    VerifiedClaim(
                        **claim.model_dump(),
                        result="uncertain",
                        confidence=0,
                        rationale="已审核知识库没有检索到足以核验该主张的证据。",
                        citations=[],
                    )
                )
                continue
            if not decision:
                raise ClaimVerificationError("核验结果缺少对应主张")
            if any(
                citation_index < 1 or citation_index > len(evidence)
                for citation_index in decision.citation_indexes
            ):
                raise ClaimVerificationError("核验结果引用了不存在的知识证据")
            citations = [
                self._citation(evidence[citation_index - 1])
                for citation_index in dict.fromkeys(decision.citation_indexes)
            ]
            result = decision.result
            confidence = decision.confidence
            rationale = decision.rationale
            if result in {"supported", "contradicted"} and not citations:
                result = "uncertain"
                confidence = min(confidence, 0.5)
                rationale = "模型未提供可追溯引用，不能形成明确事实结论。"
            if result == "contradicted" and confidence < 0.8:
                result = "uncertain"
                rationale = "证据置信度不足，不能把该主张定性为事实错误。"
            results.append(
                VerifiedClaim(
                    **claim.model_dump(),
                    result=result,
                    confidence=confidence,
                    rationale=rationale,
                    citations=citations,
                )
            )
        return results

    @staticmethod
    def _citation(evidence: RetrievedEvidence) -> VerificationCitation:
        raw_sources = evidence.source_metadata.get("sources", [])
        source_urls = [
            str(source["url"])
            for source in raw_sources
            if isinstance(source, dict) and isinstance(source.get("url"), str)
        ][:10]
        raw_version = evidence.source_metadata.get("version")
        return VerificationCitation(
            chunk_id=evidence.chunk_id,
            title=evidence.title,
            quote=evidence.content[:1_500],
            version=str(raw_version)[:50] if raw_version else None,
            source_urls=source_urls,
        )

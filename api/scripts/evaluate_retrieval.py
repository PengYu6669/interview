import asyncio
import json
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from interview_copilot.application.retrieval.search import RagSearchService
from interview_copilot.config import get_settings
from interview_copilot.infrastructure.database import SessionFactory
from interview_copilot.infrastructure.rag_store import PostgresRagSearchRepository
from interview_copilot.providers.doubao_embedding import DoubaoEmbeddingProvider


class RetrievalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    case_type: Literal["positive", "confusing", "no_answer"]
    query: str
    expected_title: str | None


class RetrievalEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    minimum_recall_at_5: float = Field(ge=0, le=1)
    minimum_mrr: float = Field(ge=0, le=1)
    minimum_top_1_accuracy: float = Field(ge=0, le=1)
    minimum_no_answer_accuracy: float = Field(ge=0, le=1)
    cases: list[RetrievalCase] = Field(min_length=1)


async def main() -> None:
    evaluation_path = Path(__file__).parents[1] / "evaluations" / "retrieval_cases.json"
    evaluation = RetrievalEvaluation.model_validate_json(
        evaluation_path.read_text(encoding="utf-8")
    )
    settings = get_settings()
    embedding = DoubaoEmbeddingProvider(
        api_key=settings.doubao_embedding_api_key,
        endpoint=settings.doubao_embedding_endpoint,
        model=settings.doubao_embedding_model,
        dimensions=settings.doubao_embedding_dimensions,
    )
    reciprocal_ranks: list[float] = []
    top_1_hits: list[bool] = []
    no_answer_hits: list[bool] = []
    with SessionFactory() as session:
        search = RagSearchService(PostgresRagSearchRepository(session), embedding)
        for case in evaluation.cases:
            results = await search.search(
                user_id=uuid4(),
                query=case.query,
                corpus_types=["knowledge"],
                source_types=["curated_knowledge_pack"],
                limit=5,
            )
            rank = next(
                (
                    index
                    for index, item in enumerate(results, start=1)
                    if case.expected_title is not None
                    and item.title == case.expected_title
                ),
                None,
            )
            if case.case_type == "no_answer":
                no_answer_hits.append(not results)
            else:
                reciprocal_ranks.append(0 if rank is None else 1 / rank)
                top_1_hits.append(rank == 1)
            print(
                json.dumps(
                    {
                        "case": case.id,
                        "case_type": case.case_type,
                        "rank": rank,
                        "top_results": [
                            {
                                "title": item.title,
                                "score": round(item.score, 3),
                                "matched_by": item.matched_by,
                            }
                            for item in results[:3]
                        ],
                    },
                    ensure_ascii=False,
                )
            )
    recall_at_5 = sum(value > 0 for value in reciprocal_ranks) / len(reciprocal_ranks)
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
    top_1_accuracy = sum(top_1_hits) / len(top_1_hits)
    no_answer_accuracy = sum(no_answer_hits) / len(no_answer_hits)
    print(
        json.dumps(
            {
                "version": evaluation.version,
                "cases": len(evaluation.cases),
                "recall_at_5": round(recall_at_5, 3),
                "mrr": round(mrr, 3),
                "top_1_accuracy": round(top_1_accuracy, 3),
                "no_answer_accuracy": round(no_answer_accuracy, 3),
            },
            ensure_ascii=False,
        )
    )
    if recall_at_5 < evaluation.minimum_recall_at_5:
        raise SystemExit("Retrieval evaluation did not meet the configured threshold")
    if mrr < evaluation.minimum_mrr:
        raise SystemExit("Retrieval MRR did not meet the configured threshold")
    if top_1_accuracy < evaluation.minimum_top_1_accuracy:
        raise SystemExit("Retrieval Top-1 accuracy did not meet the configured threshold")
    if no_answer_accuracy < evaluation.minimum_no_answer_accuracy:
        raise SystemExit("Retrieval no-answer accuracy did not meet the configured threshold")


if __name__ == "__main__":
    asyncio.run(main())

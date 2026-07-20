import asyncio

from sqlalchemy import select

from interview_copilot.application.question_workflows import QuestionWorkflowService
from interview_copilot.application.retrieval.indexing import RagIndexingService
from interview_copilot.config import get_settings
from interview_copilot.infrastructure.database import SessionFactory
from interview_copilot.infrastructure.questions import QuestionRecord
from interview_copilot.infrastructure.rag_store import SqlAlchemyRagStore
from interview_copilot.providers.dashscope_embedding import DashScopeEmbeddingProvider


async def main() -> None:
    settings = get_settings()
    with SessionFactory() as session:
        embedding = DashScopeEmbeddingProvider(
            api_key=settings.dashscope_api_key,
            endpoint=settings.dashscope_embedding_endpoint,
            model=settings.dashscope_embedding_model,
            dimensions=settings.dashscope_embedding_dimensions,
        )
        service = QuestionWorkflowService(
            session,
            rag_indexing=RagIndexingService(SqlAlchemyRagStore(session), embedding),
        )
        questions = session.scalars(
            select(QuestionRecord).where(QuestionRecord.published.is_(True))
        ).all()
        for index, question in enumerate(questions, start=1):
            await service.index_question(question)
            session.commit()
            print(f"已索引 {index}/{len(questions)}：{question.title}")


if __name__ == "__main__":
    asyncio.run(main())

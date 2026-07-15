import asyncio
from uuid import NAMESPACE_URL, uuid5

from interview_copilot.application.retrieval.indexing import RagIndexingService
from interview_copilot.config import get_settings
from interview_copilot.domain.retrieval import RagDocumentInput
from interview_copilot.infrastructure.database import SessionFactory
from interview_copilot.infrastructure.rag_store import SqlAlchemyRagStore
from interview_copilot.knowledge_packs import load_knowledge_packs
from interview_copilot.providers.doubao_embedding import DoubaoEmbeddingProvider


async def main() -> None:
    settings = get_settings()
    embedding = DoubaoEmbeddingProvider(
        api_key=settings.doubao_embedding_api_key,
        endpoint=settings.doubao_embedding_endpoint,
        model=settings.doubao_embedding_model,
        dimensions=settings.doubao_embedding_dimensions,
    )
    with SessionFactory() as session:
        indexing = RagIndexingService(SqlAlchemyRagStore(session), embedding)
        for pack in load_knowledge_packs():
            manifest = pack.manifest
            indexed = await indexing.index(
                RagDocumentInput(
                    owner_user_id=None,
                    corpus_type="knowledge",
                    source_type="curated_knowledge_pack",
                    source_id=uuid5(
                        NAMESPACE_URL,
                        f"interview-copilot:knowledge-pack:{manifest.id}",
                    ),
                    visibility="public",
                    title=manifest.title,
                    text=pack.content,
                    metadata={
                        "pack_id": manifest.id,
                        "version": manifest.version,
                        "updated_at": manifest.updated_at.isoformat(),
                        "sources": [
                            source.model_dump(mode="json") for source in manifest.sources
                        ],
                    },
                )
            )
            print(f"Indexed {manifest.id}: {indexed.chunk_count} chunks")
        session.commit()


if __name__ == "__main__":
    asyncio.run(main())

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from interview_copilot.config import get_settings
from interview_copilot.infrastructure.agent_audit import AgentToolAuditRecord  # noqa: F401
from interview_copilot.infrastructure.boards import InterviewBoardSnapshotRecord  # noqa: F401
from interview_copilot.infrastructure.career import (  # noqa: F401
    CareerPlanDraftRecord,
    CareerProfileRecord,
    WeeklyPlanItemRecord,
    WeeklyPlanRecord,
)
from interview_copilot.infrastructure.coaching import CoachingSessionRecord  # noqa: F401
from interview_copilot.infrastructure.coding import (  # noqa: F401
    InterviewCodingRunRecord,
    InterviewCodingSnapshotRecord,
)
from interview_copilot.infrastructure.database import Base
from interview_copilot.infrastructure.drafts import TrainingDraftRecord  # noqa: F401
from interview_copilot.infrastructure.interviews import (  # noqa: F401
    InterviewSessionRecord,
    InterviewTurnRecord,
)
from interview_copilot.infrastructure.jobs import AiJobRecord  # noqa: F401
from interview_copilot.infrastructure.questions import QuestionRecord  # noqa: F401
from interview_copilot.infrastructure.rag import RagDocumentRecord  # noqa: F401
from interview_copilot.infrastructure.resume_extractions import (  # noqa: F401
    ResumeExtractionCacheRecord,
)

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata

MIGRATION_MANAGED_INDEXES = {
    "ix_rag_chunks_content_trgm",
    "ix_rag_chunks_search_vector",
}


def include_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    del object_, reflected, compare_to
    return not (type_ == "index" and name in MIGRATION_MANAGED_INDEXES)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

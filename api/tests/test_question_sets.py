from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from interview_copilot.application.question_sets import QuestionSetService
from interview_copilot.infrastructure.database import Base, UserRecord
from interview_copilot.infrastructure.questions import QuestionRecord


def test_custom_question_set_keeps_order_and_rejects_foreign_private_questions() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        owner = UserRecord(
            username="set-owner",
            email="set-owner@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        stranger = UserRecord(
            username="set-stranger",
            email="set-stranger@example.com",
            password_hash="hash",
            created_at=datetime.now(UTC),
        )
        session.add_all([owner, stranger])
        session.flush()
        owned = _question("owned-set-question", owner.id)
        public = _question("public-set-question", None, published=True)
        foreign = _question("foreign-set-question", stranger.id)
        session.add_all([owned, public, foreign])
        session.commit()
        service = QuestionSetService(session)

        created = service.create_custom(
            user_id=owner.id, name="面试冲刺", question_ids=[public.id, owned.id]
        )

        assert [item.id for item in created.questions] == [public.id, owned.id]
        assert created.kind == "custom"
        with pytest.raises(ValueError, match="无权访问"):
            service.create_custom(user_id=owner.id, name="越权集合", question_ids=[foreign.id])


def _question(slug: str, owner_user_id: UUID | None, *, published: bool = False) -> QuestionRecord:
    return QuestionRecord(
        slug=slug,
        title=slug,
        prompt="请回答",
        difficulty="基础",
        question_type="原理",
        intent="测试",
        answer_outline=["结论", "展开"],
        common_mistakes=["遗漏边界"],
        published=published,
        owner_user_id=owner_user_id,
        created_at=datetime.now(UTC),
    )

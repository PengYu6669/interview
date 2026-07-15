from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session

from interview_copilot.domain.interviews import (
    InterviewPhaseSummary,
    InterviewPlan,
    InterviewRuntimeData,
    InterviewSessionData,
)
from interview_copilot.domain.retrieval import RagDocumentInput, RetrievedEvidence
from interview_copilot.domain.training import TrainingContext
from interview_copilot.infrastructure.drafts import (
    TrainingDraftQuestionRecord,
    TrainingDraftRecord,
    get_owned_draft,
)
from interview_copilot.infrastructure.interviews import InterviewSessionRecord, InterviewTurnRecord
from interview_copilot.infrastructure.questions import QuestionRecord

from .retrieval.indexing import RagIndexingService
from .retrieval.search import RagSearchService


class InterviewPlanningError(RuntimeError):
    pass


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class InterviewPlanGenerator(Protocol):
    model_name: str
    prompt_version: str

    async def generate(
        self,
        *,
        resume_text: str,
        jd: str,
        target_role: str,
        target_company: str,
        target_level: str,
        interview_round: str,
        interview_type: str,
        mode: str,
        duration_minutes: int,
        pressure_level: int,
        depth_level: int,
        guidance_level: int,
        question_bank_context: list[dict[str, object]],
        rag_context: dict[str, list[dict[str, object]]],
        training_focus: str,
        extraction: dict | None,
    ) -> InterviewPlan: ...


class InterviewPlanningService:
    def __init__(
        self,
        session: Session,
        generator: InterviewPlanGenerator | None = None,
        *,
        rag_indexing: RagIndexingService | None = None,
        rag_search: RagSearchService | None = None,
    ) -> None:
        self._session = session
        self._generator = generator
        self._rag_indexing = rag_indexing
        self._rag_search = rag_search

    async def create(self, *, user_id: UUID, draft_id: UUID) -> InterviewSessionData:
        if not self._generator:
            raise InterviewPlanningError("面试计划生成器尚未配置")
        draft = get_owned_draft(self._session, draft_id, user_id)
        if not draft:
            raise LookupError("找不到可用于生成面试的训练草稿")
        if not draft.extraction:
            raise ValueError("请先完成简历结构化提取并保存校正结果")

        existing = self._session.scalar(
            select(InterviewSessionRecord).where(
                InterviewSessionRecord.draft_id == draft.id,
                InterviewSessionRecord.user_id == user_id,
            )
        )
        if existing:
            return self._to_domain(existing)

        selected_question_ids = self._session.scalars(
            select(TrainingDraftQuestionRecord.question_id).where(
                TrainingDraftQuestionRecord.draft_id == draft.id
            )
        ).all()
        selected_questions = self._session.scalars(
            select(QuestionRecord).where(QuestionRecord.id.in_(selected_question_ids))
        ).all() if selected_question_ids else []
        rag_context = await self._prepare_rag_context(
            user_id=user_id,
            draft=draft,
            selected_question_ids=list(selected_question_ids),
        )
        plan = await self._generator.generate(
            resume_text=draft.resume_text,
            jd=draft.jd,
            target_role=draft.target_role,
            target_company=draft.target_company,
            target_level=draft.target_level,
            interview_round=draft.interview_round,
            interview_type=draft.interview_type,
            mode=draft.mode,
            duration_minutes=draft.duration_minutes,
            pressure_level=draft.pressure_level,
            depth_level=draft.depth_level,
            guidance_level=draft.guidance_level,
            question_bank_context=[
                {
                    "title": question.title,
                    "prompt": question.prompt,
                    "intent": question.intent,
                    "answer_outline": question.answer_outline,
                    "common_mistakes": question.common_mistakes,
                }
                for question in selected_questions
            ],
            rag_context=rag_context,
            training_focus=draft.training_focus,
            extraction=draft.extraction,
        )
        planned_minutes = sum(phase.minutes for phase in plan.phases)
        if planned_minutes != draft.duration_minutes:
            message = (
                f"面试计划总时长为 {planned_minutes} 分钟，"
                f"与设定的 {draft.duration_minutes} 分钟不一致"
            )
            raise InterviewPlanningError(message)
        candidate_qa_indexes = [
            index for index, phase in enumerate(plan.phases) if phase.kind == "candidate_qa"
        ]
        if len(candidate_qa_indexes) > 1 or (
            candidate_qa_indexes and candidate_qa_indexes[0] != len(plan.phases) - 1
        ):
            raise InterviewPlanningError("候选人反问阶段必须唯一且位于面试计划最后")
        if draft.duration_minutes >= 30 and not candidate_qa_indexes:
            raise InterviewPlanningError("30 分钟及以上的面试计划必须包含最终反问阶段")

        record = InterviewSessionRecord(
            user_id=user_id,
            draft_id=draft.id,
            status="planned",
            target_role=plan.target_role,
            target_company=draft.target_company,
            target_level=draft.target_level,
            interview_round=draft.interview_round,
            interview_type=draft.interview_type,
            mode=draft.mode,
            duration_minutes=draft.duration_minutes,
            pressure_level=draft.pressure_level,
            depth_level=draft.depth_level,
            guidance_level=draft.guidance_level,
            training_focus=draft.training_focus,
            summary=plan.summary,
            plan=plan.model_dump(mode="json"),
            model=self._generator.model_name,
            prompt_version=self._generator.prompt_version,
            current_phase_index=0,
            current_question_index=0,
            created_at=datetime.now(UTC),
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            existing = self._session.scalar(
                select(InterviewSessionRecord).where(
                    InterviewSessionRecord.draft_id == draft.id,
                    InterviewSessionRecord.user_id == user_id,
                )
            )
            if existing:
                return self._to_domain(existing)
            raise InterviewPlanningError("面试会话保存失败") from exc
        self._session.refresh(record)
        return self._to_domain(record)

    async def _prepare_rag_context(
        self,
        *,
        user_id: UUID,
        draft: TrainingDraftRecord,
        selected_question_ids: list[UUID],
    ) -> dict[str, list[dict[str, object]]]:
        if not self._rag_indexing or not self._rag_search:
            raise InterviewPlanningError("三角 RAG 服务尚未配置")
        draft_id = draft.id
        target_role = draft.target_role
        training_focus = draft.training_focus
        await self._rag_indexing.index(
            RagDocumentInput(
                owner_user_id=user_id,
                corpus_type="candidate",
                source_type="resume",
                source_id=draft_id,
                title=draft.resume_filename,
                text=draft.resume_text,
                metadata={"draft_id": str(draft_id)},
            )
        )
        job_text = "\n".join(
            item
            for item in [
                f"目标岗位：{target_role}",
                f"目标公司：{draft.target_company}",
                f"目标职级：{draft.target_level}",
                f"面试轮次：{draft.interview_round}",
                draft.jd,
            ]
            if item
        )
        await self._rag_indexing.index(
            RagDocumentInput(
                owner_user_id=user_id,
                corpus_type="job",
                source_type="jd",
                source_id=draft_id,
                title=f"{target_role}岗位上下文",
                text=job_text,
                metadata={"draft_id": str(draft_id)},
            )
        )
        focus = f"{target_role} {training_focus}".strip()
        candidate = await self._rag_search.search(
            user_id=user_id,
            query=f"{focus} 项目经验 技术实现 个人职责 方案取舍 量化结果",
            corpus_types=["candidate"],
            source_ids=[draft_id],
            limit=4,
        )
        job = await self._rag_search.search(
            user_id=user_id,
            query=f"{focus} 岗位要求 核心职责 业务目标 能力要求",
            corpus_types=["job"],
            source_ids=[draft_id],
            limit=3,
        )
        knowledge = await self._rag_search.search(
            user_id=user_id,
            query=f"{focus} 技术面试 核心知识 实现边界",
            corpus_types=["knowledge"],
            source_types=["question"],
            source_ids=selected_question_ids,
            limit=4,
        )
        return {
            "candidate": self._evidence_payload(candidate, "C"),
            "job": self._evidence_payload(job, "J"),
            "knowledge": self._evidence_payload(knowledge, "K"),
        }

    @staticmethod
    def _evidence_payload(
        evidence: list[RetrievedEvidence], prefix: str
    ) -> list[dict[str, object]]:
        return [
            {
                "ref": f"{prefix}{index}",
                "chunk_id": str(item.chunk_id),
                "title": item.title,
                "heading_path": item.heading_path,
                "content": item.content[:1600],
                "score": round(item.score, 4),
                "matched_by": item.matched_by,
            }
            for index, item in enumerate(evidence, 1)
        ]

    def get(self, *, user_id: UUID, session_id: UUID) -> InterviewSessionData:
        record = self._session.scalar(
            select(InterviewSessionRecord).where(
                InterviewSessionRecord.id == session_id,
                InterviewSessionRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到这场面试会话")
        return self._to_domain(record)

    def start(self, *, user_id: UUID, session_id: UUID) -> InterviewRuntimeData:
        record = self._owned_record(user_id=user_id, session_id=session_id)
        if record.status not in {"planned", "started", "paused"}:
            raise ValueError("这场面试当前不能开始")
        if record.status in {"planned", "paused"}:
            plan = InterviewPlan.model_validate(record.plan)
            now = datetime.now(UTC)
            if record.paused_at:
                record.accumulated_pause_seconds += max(
                    0, int((now - _utc(record.paused_at)).total_seconds())
                )
                record.paused_at = None
            record.status = "started"
            record.started_at = record.started_at or now
            record.active_question = record.active_question or plan.phases[0].questions[0].prompt
            self._session.commit()
            self._session.refresh(record)
        return interview_runtime_data(record)

    def pause(self, *, user_id: UUID, session_id: UUID) -> InterviewRuntimeData:
        record = self._owned_record(user_id=user_id, session_id=session_id)
        if record.status != "started":
            raise ValueError("只有进行中的面试可以暂停")
        record.status = "paused"
        record.paused_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(record)
        return interview_runtime_data(record)

    def end(self, *, user_id: UUID, session_id: UUID) -> InterviewRuntimeData:
        record = self._owned_record(user_id=user_id, session_id=session_id)
        if record.status not in {"started", "paused"}:
            raise ValueError("这场面试当前不能结束")
        now = datetime.now(UTC)
        if record.paused_at:
            record.accumulated_pause_seconds += max(
                0, int((now - _utc(record.paused_at)).total_seconds())
            )
            record.paused_at = None
        record.status = "ended"
        record.completed_at = now
        record.active_question = None
        self._session.commit()
        self._session.refresh(record)
        return interview_runtime_data(record)

    def runtime(self, *, user_id: UUID, session_id: UUID) -> InterviewRuntimeData:
        record = self._owned_record(user_id=user_id, session_id=session_id)
        if not record.started_at:
            raise ValueError("这场面试尚未开始")
        return interview_runtime_data(record)

    def _owned_record(self, *, user_id: UUID, session_id: UUID) -> InterviewSessionRecord:
        record = self._session.scalar(
            select(InterviewSessionRecord).where(
                InterviewSessionRecord.id == session_id,
                InterviewSessionRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到这场面试会话")
        return record

    @staticmethod
    def _to_domain(record: InterviewSessionRecord) -> InterviewSessionData:
        plan = InterviewPlan.model_validate(record.plan)
        context = TrainingContext.model_validate(
            {
                "target_company": record.target_company,
                "target_level": record.target_level,
                "interview_round": record.interview_round,
                "interview_type": record.interview_type,
            }
        )
        return InterviewSessionData(
            id=record.id,
            draft_id=record.draft_id,
            status=record.status,
            target_role=record.target_role,
            target_company=context.target_company,
            target_level=context.target_level,
            interview_round=context.interview_round,
            interview_type=context.interview_type,
            mode=record.mode,
            duration_minutes=record.duration_minutes,
            pressure_level=record.pressure_level,
            depth_level=record.depth_level,
            guidance_level=record.guidance_level,
            training_focus=record.training_focus,
            summary=record.summary,
            phases=[
                InterviewPhaseSummary(
                    name=phase.name,
                    kind=phase.kind,
                    minutes=phase.minutes,
                    skills=phase.skills,
                    question_count=len(phase.questions),
                )
                for phase in plan.phases
            ],
            model=record.model,
            prompt_version=record.prompt_version,
            created_at=record.created_at,
        )


def interview_runtime_data(record: InterviewSessionRecord) -> InterviewRuntimeData:
    if not record.started_at:
        raise InterviewPlanningError("面试会话缺少开始时间")
    plan = InterviewPlan.model_validate(record.plan)
    context = TrainingContext.model_validate(
        {
            "target_company": record.target_company,
            "target_level": record.target_level,
            "interview_round": record.interview_round,
            "interview_type": record.interview_type,
        }
    )
    total_questions = sum(len(item.questions) for item in plan.phases)
    answered = (
        sum(len(item.questions) for item in plan.phases[: record.current_phase_index])
        + record.current_question_index
    )
    current_question_number = answered + 1
    if record.status in {"completed", "ended"}:
        current_question = None
        if record.status == "completed":
            answered = total_questions
    else:
        try:
            phase = plan.phases[record.current_phase_index]
            question = phase.questions[record.current_question_index]
        except IndexError as exc:
            raise InterviewPlanningError("面试会话进度数据无效") from exc
        current_question = record.active_question or question.prompt
    effective_now = _utc(record.paused_at or record.completed_at or datetime.now(UTC))
    elapsed_seconds = max(
        0,
        int((effective_now - _utc(record.started_at)).total_seconds())
        - record.accumulated_pause_seconds,
    )
    remaining_seconds = max(0, record.duration_minutes * 60 - elapsed_seconds)
    latest_turn = None
    session = object_session(record)
    if record.id is not None and session is not None:
        latest_turn = session.scalar(
            select(InterviewTurnRecord)
            .where(InterviewTurnRecord.session_id == record.id)
            .order_by(InterviewTurnRecord.sequence.desc())
            .limit(1)
        )
    return InterviewRuntimeData(
        id=record.id,
        status=record.status,
        target_role=record.target_role,
        target_company=context.target_company,
        target_level=context.target_level,
        interview_round=context.interview_round,
        interview_type=context.interview_type,
        mode=record.mode,
        duration_minutes=record.duration_minutes,
        pressure_level=record.pressure_level,
        depth_level=record.depth_level,
        guidance_level=record.guidance_level,
        training_focus=record.training_focus,
        phases=[
            InterviewPhaseSummary(
                name=item.name,
                kind=item.kind,
                minutes=item.minutes,
                skills=item.skills,
                question_count=len(item.questions),
            )
            for item in plan.phases
        ],
        current_phase_index=record.current_phase_index,
        current_question_index=record.current_question_index,
        current_question=current_question,
        current_question_number=min(current_question_number, total_questions),
        current_question_kind="follow_up" if record.follow_up_count > 0 else "main",
        follow_up_count=record.follow_up_count,
        interviewer_transition=latest_turn.transition if latest_turn else None,
        interviewer_reply=latest_turn.interviewer_reply if latest_turn else None,
        closing_statement=(
            "好的，今天的模拟面试就到这里。感谢你的时间，稍后可以查看基于回答证据生成的复盘报告。"
            if record.status == "completed"
            else None
        ),
        opening_statement=(
            f"你好，我是今天的面试官林老师。这场{record.target_role}模拟面试大约"
            f"{record.duration_minutes}分钟，我们会从{plan.phases[0].name}开始。"
            "你可以像正式面试一样思考和回答，不清楚的问题也可以直接说明。"
        ),
        answered_questions=answered,
        total_questions=total_questions,
        started_at=record.started_at,
        remaining_seconds=remaining_seconds,
    )

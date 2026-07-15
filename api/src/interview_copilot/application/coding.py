from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from interview_copilot.domain.coding import (
    CodingExecutionResult,
    CodingProblemSpec,
    CodingRunData,
    CodingRunRequest,
    CodingSnapshotData,
    CodingSnapshotRequest,
    CodingWorkspaceData,
)
from interview_copilot.domain.interviews import InterviewPlan
from interview_copilot.infrastructure.coding import (
    InterviewCodingRunRecord,
    InterviewCodingSnapshotRecord,
)
from interview_copilot.infrastructure.interviews import InterviewSessionRecord


class CodingExecutor(Protocol):
    async def execute(
        self, *, source: str, problem: CodingProblemSpec
    ) -> CodingExecutionResult: ...


class CodingConflictError(RuntimeError):
    def __init__(self, current: CodingSnapshotData) -> None:
        super().__init__("代码已在其他标签页更新，请先加载最新版本")
        self.current = current


class InterviewCodingService:
    def __init__(self, session: Session, executor: CodingExecutor | None = None) -> None:
        self._session = session
        self._executor = executor

    def get_workspace(self, *, user_id: UUID, session_id: UUID) -> CodingWorkspaceData:
        record, problem = self._active_context(user_id=user_id, session_id=session_id)
        snapshot = self._latest_snapshot(record)
        return CodingWorkspaceData(
            problem=problem,
            snapshot=self._to_snapshot(snapshot) if snapshot else None,
        )

    def save(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request: CodingSnapshotRequest,
    ) -> CodingWorkspaceData:
        session, problem = self._active_context(user_id=user_id, session_id=session_id)
        existing = self._session.scalar(
            select(InterviewCodingSnapshotRecord).where(
                InterviewCodingSnapshotRecord.user_id == user_id,
                InterviewCodingSnapshotRecord.client_snapshot_id == request.client_snapshot_id,
            )
        )
        if existing:
            return CodingWorkspaceData(problem=problem, snapshot=self._to_snapshot(existing))
        latest = self._latest_snapshot(session)
        snapshot_count = self._session.scalar(
            select(func.count(InterviewCodingSnapshotRecord.id)).where(
                InterviewCodingSnapshotRecord.session_id == session_id,
                InterviewCodingSnapshotRecord.phase_index == session.current_phase_index,
                InterviewCodingSnapshotRecord.question_index == session.current_question_index,
            )
        )
        if int(snapshot_count or 0) >= 100:
            raise ValueError("当前题目的代码版本已达到 100 个上限")
        next_revision = 0 if latest is None else latest.revision + 1
        if request.base_revision != next_revision:
            if latest is None:
                raise ValueError("代码版本状态无效，请重新加载")
            raise CodingConflictError(self._to_snapshot(latest))
        record = InterviewCodingSnapshotRecord(
            session_id=session_id,
            user_id=user_id,
            phase_index=session.current_phase_index,
            question_index=session.current_question_index,
            revision=next_revision,
            client_snapshot_id=request.client_snapshot_id,
            source=request.source,
            complexity_notes=request.complexity_notes.strip(),
            created_at=datetime.now(UTC),
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            current = self._latest_snapshot(session)
            if current:
                raise CodingConflictError(self._to_snapshot(current)) from None
            raise ValueError("代码保存失败，请重新加载") from None
        self._session.refresh(record)
        return CodingWorkspaceData(problem=problem, snapshot=self._to_snapshot(record))

    async def run(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request: CodingRunRequest,
    ) -> CodingRunData:
        existing = self._session.scalar(
            select(InterviewCodingRunRecord).where(
                InterviewCodingRunRecord.user_id == user_id,
                InterviewCodingRunRecord.client_request_id == request.client_request_id,
            )
        )
        if existing:
            if existing.session_id != session_id:
                raise ValueError("该运行请求标识已用于其他面试")
            return self._to_run(existing)
        session, problem = self._active_context(
            user_id=user_id, session_id=session_id, require_started=True
        )
        snapshot = self._latest_snapshot(session)
        if not snapshot:
            raise ValueError("请先保存代码再运行")
        if snapshot.revision != request.snapshot_revision:
            raise CodingConflictError(self._to_snapshot(snapshot))
        run_count = self._session.scalar(
            select(func.count(InterviewCodingRunRecord.id)).where(
                InterviewCodingRunRecord.session_id == session_id,
                InterviewCodingRunRecord.snapshot_id == snapshot.id,
            )
        )
        if int(run_count or 0) >= 30:
            raise ValueError("当前代码版本已达到 30 次运行上限，请修改并保存新版本")
        if not self._executor:
            raise RuntimeError("Coding 沙箱尚未配置")
        result = await self._executor.execute(source=snapshot.source, problem=problem)
        record = InterviewCodingRunRecord(
            session_id=session_id,
            user_id=user_id,
            snapshot_id=snapshot.id,
            client_request_id=request.client_request_id,
            status=result.status,
            tests=[item.model_dump(mode="json") for item in result.tests],
            duration_ms=result.duration_ms,
            error=result.error,
            created_at=datetime.now(UTC),
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            concurrent = self._session.scalar(
                select(InterviewCodingRunRecord).where(
                    InterviewCodingRunRecord.user_id == user_id,
                    InterviewCodingRunRecord.client_request_id == request.client_request_id,
                )
            )
            if concurrent:
                return self._to_run(concurrent)
            raise
        self._session.refresh(record)
        return self._to_run(record)

    def _active_context(
        self, *, user_id: UUID, session_id: UUID, require_started: bool = False
    ) -> tuple[InterviewSessionRecord, CodingProblemSpec]:
        record = self._session.scalar(
            select(InterviewSessionRecord).where(
                InterviewSessionRecord.id == session_id,
                InterviewSessionRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到面试会话")
        allowed = {"started"} if require_started else {"started", "paused"}
        if record.status not in allowed:
            raise ValueError("当前面试状态不能使用 Coding Board")
        plan = InterviewPlan.model_validate(record.plan)
        phase = plan.phases[record.current_phase_index]
        if phase.kind != "coding":
            raise ValueError("当前不是 Coding 面试阶段")
        problem = phase.questions[record.current_question_index].coding_spec
        if problem is None:
            raise ValueError("当前 Coding 题缺少结构化测试数据")
        return record, problem

    def _latest_snapshot(
        self, session: InterviewSessionRecord
    ) -> InterviewCodingSnapshotRecord | None:
        return self._session.scalar(
            select(InterviewCodingSnapshotRecord)
            .where(
                InterviewCodingSnapshotRecord.session_id == session.id,
                InterviewCodingSnapshotRecord.user_id == session.user_id,
                InterviewCodingSnapshotRecord.phase_index == session.current_phase_index,
                InterviewCodingSnapshotRecord.question_index == session.current_question_index,
            )
            .order_by(InterviewCodingSnapshotRecord.revision.desc())
        )

    @staticmethod
    def _to_snapshot(record: InterviewCodingSnapshotRecord) -> CodingSnapshotData:
        return CodingSnapshotData.model_validate(record, from_attributes=True)

    @staticmethod
    def _to_run(record: InterviewCodingRunRecord) -> CodingRunData:
        return CodingRunData.model_validate(record, from_attributes=True)

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from interview_copilot.domain.board import (
    BoardSnapshotData,
    BoardSnapshotRequest,
    BoardState,
)
from interview_copilot.domain.interviews import InterviewPlan
from interview_copilot.infrastructure.boards import InterviewBoardSnapshotRecord
from interview_copilot.infrastructure.interviews import InterviewSessionRecord


class BoardConflictError(RuntimeError):
    def __init__(self, current: BoardSnapshotData) -> None:
        super().__init__("白板已在其他标签页更新，请先加载最新版本")
        self.current = current


class InterviewBoardService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest(self, *, user_id: UUID, session_id: UUID) -> BoardSnapshotData | None:
        self._owned_session(user_id=user_id, session_id=session_id)
        record = self._session.scalar(
            select(InterviewBoardSnapshotRecord)
            .where(
                InterviewBoardSnapshotRecord.user_id == user_id,
                InterviewBoardSnapshotRecord.session_id == session_id,
            )
            .order_by(InterviewBoardSnapshotRecord.revision.desc())
        )
        return self._to_domain(record) if record else None

    def save(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        request: BoardSnapshotRequest,
    ) -> BoardSnapshotData:
        session = self._owned_session(user_id=user_id, session_id=session_id)
        if session.status not in {"started", "paused"}:
            raise ValueError("只有进行中的面试可以保存白板")
        plan = InterviewPlan.model_validate(session.plan)
        if plan.phases[session.current_phase_index].kind != "system_design":
            raise ValueError("只有系统设计阶段可以保存白板")
        existing = self._session.scalar(
            select(InterviewBoardSnapshotRecord).where(
                InterviewBoardSnapshotRecord.user_id == user_id,
                InterviewBoardSnapshotRecord.client_snapshot_id == request.client_snapshot_id,
            )
        )
        if existing:
            return self._to_domain(existing)
        max_revision = self._session.scalar(
            select(func.coalesce(func.max(InterviewBoardSnapshotRecord.revision), -1)).where(
                InterviewBoardSnapshotRecord.session_id == session_id,
                InterviewBoardSnapshotRecord.user_id == user_id,
            )
        )
        current_revision = int(max_revision if max_revision is not None else -1) + 1
        current = self.get_latest(user_id=user_id, session_id=session_id)
        if request.base_revision != current_revision:
            if current is None:
                raise ValueError("白板版本状态无效，请重新加载")
            raise BoardConflictError(current)
        record = InterviewBoardSnapshotRecord(
            session_id=session_id,
            user_id=user_id,
            revision=current_revision,
            client_snapshot_id=request.client_snapshot_id,
            state=request.state.model_dump(mode="json"),
            created_at=datetime.now(UTC),
        )
        self._session.add(record)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            latest = self.get_latest(user_id=user_id, session_id=session_id)
            if latest:
                raise BoardConflictError(latest) from None
            raise ValueError("白板保存失败，请重新加载") from None
        self._session.refresh(record)
        return self._to_domain(record)

    def _owned_session(self, *, user_id: UUID, session_id: UUID) -> InterviewSessionRecord:
        record = self._session.scalar(
            select(InterviewSessionRecord).where(
                InterviewSessionRecord.id == session_id,
                InterviewSessionRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到面试会话")
        return record

    @staticmethod
    def _to_domain(record: InterviewBoardSnapshotRecord) -> BoardSnapshotData:
        return BoardSnapshotData(
            id=record.id,
            session_id=record.session_id,
            revision=record.revision,
            client_snapshot_id=record.client_snapshot_id,
            state=BoardState.model_validate(record.state),
            created_at=record.created_at,
        )

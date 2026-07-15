from collections import defaultdict
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from interview_copilot.domain.coaching import CoachingDecision, CoachingMode
from interview_copilot.domain.interviews import InterviewReportContent, InterviewSkillScore
from interview_copilot.domain.profile import (
    AbilityKlinePoint,
    AbilityMatrixItem,
    AbilityProfileData,
    CoachingAbilityItem,
    CoachingProfileSummary,
)
from interview_copilot.infrastructure.coaching import (
    CoachingSessionRecord,
    CoachingTurnRecord,
)
from interview_copilot.infrastructure.interviews import (
    InterviewReportRecord,
    InterviewReportReviewRecord,
)


class AbilityProfileService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, *, user_id: UUID) -> AbilityProfileData:
        coaching = self._coaching_summary(user_id=user_id)
        records = self._session.scalars(
            select(InterviewReportRecord)
            .where(InterviewReportRecord.user_id == user_id)
            .order_by(InterviewReportRecord.created_at)
        ).all()
        if not records:
            return AbilityProfileData(
                report_count=0,
                average_score=None,
                average_coverage=None,
                kline=[],
                skills=[],
                next_training=None,
                coaching=coaching,
            )

        contents = [InterviewReportContent.model_validate(record.content) for record in records]
        review_records = self._session.scalars(
            select(InterviewReportReviewRecord)
            .where(
                InterviewReportReviewRecord.report_id.in_([record.id for record in records]),
                InterviewReportReviewRecord.status == "resolved",
            )
            .order_by(InterviewReportReviewRecord.created_at)
        ).all()
        latest_reviews = {
            (review.report_id, review.skill_index): review for review in review_records
        }
        kline: list[AbilityKlinePoint] = []
        previous_close: int | None = None
        next_training: str | None = None
        skill_history: dict[str, list[tuple[int, float, int, UUID, str]]] = defaultdict(list)
        for record, content in zip(records, contents, strict=True):
            close = content.overall_score
            open_score = previous_close if previous_close is not None else close
            effective_scores: list[tuple[int, InterviewSkillScore]] = []
            for index, score in enumerate(content.skill_scores):
                review = latest_reviews.get((record.id, index))
                if review and review.decision in {"excluded", "uncertain"}:
                    continue
                effective_score = (
                    review.revised_score
                    if review and review.decision == "revised" and review.revised_score is not None
                    else score.score
                )
                effective_scores.append((effective_score, score))
            if effective_scores:
                next_training = content.next_training
            skill_values = [score for score, _ in effective_scores]
            high = max([open_score, close, *skill_values])
            low = min([open_score, close, *skill_values])
            kline.append(
                AbilityKlinePoint(
                    session_id=record.session_id,
                    date=record.created_at,
                    open=open_score,
                    high=high,
                    low=low,
                    close=close,
                    evidence_coverage=content.evidence_coverage,
                    confidence=content.confidence,
                )
            )
            previous_close = close
            coverage_weight = content.evidence_coverage / 100
            for effective_score, score in effective_scores:
                finding = next(
                    (item for item in content.improvements if item.skill == score.skill),
                    None,
                )
                training_focus = (
                    (finding.improvement or finding.analysis)[:500]
                    if finding
                    else content.next_training[:500]
                )
                skill_history[score.skill].append(
                    (
                        effective_score,
                        max(0.01, score.confidence * coverage_weight),
                        len(set(score.evidence_turns)),
                        record.session_id,
                        training_focus,
                    )
                )

        skills = []
        for skill, values in skill_history.items():
            total_weight = sum(weight for _, weight, *_ in values)
            weighted_score = round(
                sum(score * weight for score, weight, *_ in values) / total_weight
            )
            weighted_confidence = min(1.0, total_weight / len(values))
            trend = values[-1][0] - values[-2][0] if len(values) > 1 else 0
            skills.append(
                AbilityMatrixItem(
                    skill=skill,
                    score=weighted_score,
                    confidence=round(weighted_confidence, 3),
                    evidence_count=sum(count for _, _, count, *_ in values),
                    report_count=len(values),
                    trend=trend,
                    source_session_id=values[-1][3],
                    training_focus=values[-1][4],
                )
            )
        skills.sort(key=lambda item: (item.score, -item.evidence_count, item.skill))

        return AbilityProfileData(
            report_count=len(records),
            average_score=round(sum(item.overall_score for item in contents) / len(contents)),
            average_coverage=round(
                sum(item.evidence_coverage for item in contents) / len(contents)
            ),
            kline=kline,
            skills=skills,
            next_training=next_training,
            coaching=coaching,
        )

    def _coaching_summary(self, *, user_id: UUID) -> CoachingProfileSummary:
        sessions = self._session.scalars(
            select(CoachingSessionRecord).where(CoachingSessionRecord.user_id == user_id)
        ).all()
        if not sessions:
            return CoachingProfileSummary(
                session_count=0,
                completed_count=0,
                skills=[],
                next_mode=None,
                next_focus=None,
            )
        session_modes: dict[UUID, CoachingMode] = {
            item.id: cast(CoachingMode, item.mode) for item in sessions
        }
        turns = self._session.scalars(
            select(CoachingTurnRecord)
            .where(CoachingTurnRecord.session_id.in_(session_modes))
            .order_by(CoachingTurnRecord.created_at)
        ).all()
        history: dict[str, list[tuple[int, float, UUID, str, CoachingMode]]] = defaultdict(list)
        for turn in turns:
            decision = CoachingDecision.model_validate(turn.decision)
            for assessment in decision.assessments:
                if assessment.status != "observed":
                    continue
                if assessment.level is None or assessment.evidence_quote is None:
                    continue
                history[assessment.key].append(
                    (
                        assessment.level,
                        assessment.confidence,
                        turn.session_id,
                        assessment.feedback,
                        session_modes[turn.session_id],
                    )
                )

        skills: list[CoachingAbilityItem] = []
        for dimension, values in history.items():
            total_weight = sum(max(0.01, confidence) for _, confidence, *_ in values)
            score = round(
                sum(level * 20 * max(0.01, confidence) for level, confidence, *_ in values)
                / total_weight
            )
            latest = values[-1]
            skills.append(
                CoachingAbilityItem(
                    dimension=dimension,
                    mode=latest[4],
                    score=score,
                    confidence=round(
                        sum(confidence for _, confidence, *_ in values) / len(values), 3
                    ),
                    evidence_count=len(values),
                    session_count=len({session_id for _, _, session_id, _, _ in values}),
                    source_session_id=latest[2],
                    latest_feedback=latest[3],
                )
            )
        skills.sort(key=lambda item: (item.score, item.dimension))
        next_skill = skills[0] if skills else None
        return CoachingProfileSummary(
            session_count=len(sessions),
            completed_count=sum(item.status == "completed" for item in sessions),
            skills=skills,
            next_mode=next_skill.mode if next_skill else None,
            next_focus=next_skill.latest_feedback if next_skill else None,
        )

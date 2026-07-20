import re
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, selectinload

from interview_copilot.application.ability_profile import AbilityProfileService
from interview_copilot.application.agent.career_planner import (
    CareerPlanAgentOutput,
    CareerPlanningAgent,
    CareerProfileAgentOutput,
)
from interview_copilot.application.agent.skills import ActivatedSkill
from interview_copilot.domain.career import (
    CareerProfile,
    CareerProfileConversationResult,
    CareerQuestionOption,
    CareerWorkspace,
    PlanningBasis,
    WeeklyPlan,
    WeeklyPlanDraft,
    WeeklyPlanItem,
)
from interview_copilot.infrastructure.career import (
    CareerPlanDraftRecord,
    CareerProfileRecord,
    WeeklyPlanItemRecord,
    WeeklyPlanRecord,
)
from interview_copilot.infrastructure.questions import (
    QuestionRecord,
    UserQuestionProgressRecord,
)
from interview_copilot.providers.deepseek_agent import DeepSeekAgentError


class CareerPlanner(Protocol):
    model_name: str
    prompt_version: str

    async def plan(
        self,
        *,
        user_data: dict[str, object],
        user_id: UUID,
        request_id: UUID,
    ) -> tuple[ActivatedSkill, CareerPlanAgentOutput]: ...

    async def profile_from_message(
        self, *, message: str, user_id: UUID, request_id: UUID
    ) -> CareerProfileAgentOutput: ...


class CareerService:
    def __init__(
        self, session: Session, planner: CareerPlanner | CareerPlanningAgent | None = None
    ) -> None:
        self._session = session
        self._planner = planner

    def get(self, *, user_id: UUID) -> CareerWorkspace:
        profile = self._session.get(CareerProfileRecord, user_id)
        plans = self._session.scalars(
            select(WeeklyPlanRecord)
            .where(WeeklyPlanRecord.user_id == user_id)
            .options(selectinload(WeeklyPlanRecord.items))
            .order_by(WeeklyPlanRecord.week_start.desc())
            .limit(12)
        ).all()
        return CareerWorkspace(
            profile=self._profile(profile),
            weekly_plan=self._plan(plans[0]) if plans else None,
            plan_history=[self._plan(item) for item in plans],
            question_options=self._question_options(
                user_id=user_id,
                limit=30,
                target_role=profile.target_role if profile else "",
            ),
        )

    def today(self, *, user_id: UUID, today: date | None = None) -> list[WeeklyPlanItem]:
        target = today or datetime.now(UTC).date()
        records = self._session.scalars(
            select(WeeklyPlanItemRecord)
            .join(WeeklyPlanRecord, WeeklyPlanRecord.id == WeeklyPlanItemRecord.plan_id)
            .where(
                WeeklyPlanRecord.user_id == user_id,
                WeeklyPlanItemRecord.scheduled_date == target,
            )
            .order_by(WeeklyPlanItemRecord.position)
        ).all()
        return [self._item(item) for item in records]

    def save_profile(self, *, user_id: UUID, profile: CareerProfile) -> CareerProfile:
        now = datetime.now(UTC)
        record = self._session.get(CareerProfileRecord, user_id)
        if not record:
            record = CareerProfileRecord(user_id=user_id, confirmed_at=now, updated_at=now)
            self._session.add(record)
        for key, value in profile.model_dump(
            exclude={"confirmed_at", "updated_at"}, mode="python"
        ).items():
            setattr(record, key, value)
        record.available_weekdays = sorted(set(record.available_weekdays))
        record.confirmed_at = now
        record.updated_at = now
        self._session.commit()
        self._session.refresh(record)
        return self._profile(record)

    def delete_profile(self, *, user_id: UUID) -> None:
        self._session.execute(
            delete(CareerProfileRecord).where(CareerProfileRecord.user_id == user_id)
        )
        self._session.commit()

    async def save_profile_from_message(
        self, *, user_id: UUID, request_id: UUID, message: str
    ) -> CareerProfileConversationResult:
        if not self._planner:
            raise RuntimeError("求职训练规划 Agent 尚未配置")
        parsed = await self._planner.profile_from_message(
            message=message,
            user_id=user_id,
            request_id=request_id,
        )
        if not parsed.ready:
            return CareerProfileConversationResult(reply=parsed.reply)
        profile = CareerProfile(
            target_role=parsed.target_role or "",
            target_level=parsed.target_level,
            target_companies=parsed.target_companies,
            preferred_cities=parsed.preferred_cities,
            weekly_hours=parsed.weekly_hours,
            available_weekdays=parsed.available_weekdays,
            preferred_time_slot=parsed.preferred_time_slot,
            constraints=parsed.constraints,
        )
        saved = self.save_profile(user_id=user_id, profile=profile)
        return CareerProfileConversationResult(reply=parsed.reply, profile=saved)

    async def create_draft(
        self,
        *,
        user_id: UUID,
        request_id: UUID,
        week_start: date,
        instruction: str = "",
        progress: Callable[[str, int], None] | None = None,
    ) -> WeeklyPlanDraft:
        if week_start.weekday() != 0:
            raise ValueError("周计划开始日期必须是周一")
        profile_record = self._session.get(CareerProfileRecord, user_id)
        if not profile_record or not profile_record.confirmed_at:
            raise ValueError("请先确认求职画像，再让 AI 面试教练规划本周")
        if not self._planner:
            raise RuntimeError("求职训练规划 Agent 尚未配置")
        profile = self._profile(profile_record)
        if progress:
            progress("正在读取画像与训练证据", 18)
        ability = AbilityProfileService(self._session).get(user_id=user_id)
        evidence_focus_value = ability.coaching.next_focus or ability.next_training
        evidence_focus = evidence_focus_value[:300] if evidence_focus_value else None
        options = self._question_options(
            user_id=user_id,
            limit=12,
            target_role=profile.target_role,
            evidence_focus=evidence_focus,
        )
        baseline_draft = None
        if instruction:
            active_plan = self._session.scalar(
                select(WeeklyPlanRecord)
                .where(
                    WeeklyPlanRecord.user_id == user_id,
                    WeeklyPlanRecord.status == "active",
                )
                .options(selectinload(WeeklyPlanRecord.items))
                .order_by(WeeklyPlanRecord.updated_at.desc())
            )
            if active_plan:
                baseline_draft = self._plan(active_plan).model_dump(mode="json")
            else:
                baseline_record = self._session.scalar(
                    select(CareerPlanDraftRecord)
                    .where(CareerPlanDraftRecord.user_id == user_id)
                    .order_by(CareerPlanDraftRecord.created_at.desc())
                )
                if baseline_record:
                    expires_at = baseline_record.expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)
                    if expires_at > datetime.now(UTC):
                        baseline_draft = baseline_record.payload
        basis = PlanningBasis(
            profile_confirmed=True,
            question_count=len(options),
            owned_question_count=sum(item.owned for item in options),
            due_question_count=sum(item.review_due for item in options),
            recent_training_count=ability.coaching.completed_count + ability.report_count,
            evidence_focus=evidence_focus,
        )
        if progress:
            progress("正在匹配题库与训练优先级", 36)
        skill, proposal = await self._planner.plan(
            user_data={
                "周一日期": week_start.isoformat(),
                "求职画像": profile.model_dump(mode="json"),
                "每周分钟预算": profile.weekly_hours * 60,
                "本周训练配比": self._training_mix(profile.weekly_hours),
                "可训练星期": profile.available_weekdays,
                "偏好时段": profile.preferred_time_slot,
                "候选题": [
                    {
                        "id": str(item.id),
                        "title": item.title,
                        "difficulty": item.difficulty,
                        "framework": item.framework,
                        "topics": item.topics[:4],
                        "review_due": item.review_due,
                        "owned": item.owned,
                    }
                    for item in options
                ],
                "训练证据重点": basis.evidence_focus,
                "用户本轮调整要求": instruction[:1_000] or None,
                "当前计划": baseline_draft,
                "专项能力": [
                    {
                        "维度": item.dimension,
                        "得分": item.score,
                        "可信度": item.confidence,
                        "最近反馈": item.latest_feedback[:160],
                    }
                    for item in ability.coaching.skills[:5]
                ],
            },
            user_id=user_id,
            request_id=request_id,
        )
        if progress:
            progress("正在校验训练配比与时间预算", 82)
        items = self._proposal_items(
            proposal=proposal,
            week_start=week_start,
            options=options,
        )
        items = self._apply_explicit_day_move(
            items=items,
            instruction=instruction,
            week_start=week_start,
        )
        self._validate_items(
            user_id=user_id, profile=profile, week_start=week_start, items=items
        )
        if any(item.owned for item in options) and not any(
            item.question_id and next(
                (option.owned for option in options if option.id == item.question_id), False
            )
            for item in items
        ):
            raise DeepSeekAgentError("规划结果没有使用可用的个人题库题目")
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=2)
        draft = WeeklyPlanDraft(
            id=uuid4(),
            week_start=week_start,
            goal=proposal.goal,
            items=items,
            basis=basis,
            model=self._planner.model_name,
            prompt_version=self._planner.prompt_version,
            skill_version=skill.metadata.version,
            expires_at=expires_at,
        )
        self._session.execute(
            delete(CareerPlanDraftRecord).where(
                CareerPlanDraftRecord.user_id == user_id,
                CareerPlanDraftRecord.expires_at <= now,
            ).execution_options(synchronize_session=False)
        )
        self._session.add(
            CareerPlanDraftRecord(
                id=draft.id,
                user_id=user_id,
                payload=draft.model_dump(mode="json"),
                created_at=now,
                expires_at=expires_at,
            )
        )
        if progress:
            progress("正在保存可编辑草稿", 94)
        self._session.commit()
        return draft

    def get_draft(self, *, user_id: UUID, draft_id: UUID) -> WeeklyPlanDraft:
        record = self._session.scalar(
            select(CareerPlanDraftRecord).where(
                CareerPlanDraftRecord.id == draft_id,
                CareerPlanDraftRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到这份规划草稿")
        if self._is_expired(record.expires_at, datetime.now(UTC)):
            raise ValueError("AI 规划草稿已过期，请重新生成")
        return WeeklyPlanDraft.model_validate(record.payload)

    def save_weekly_plan(
        self,
        *,
        user_id: UUID,
        week_start: date,
        goal: str,
        items: list[WeeklyPlanItem],
        status: str,
        draft_id: UUID | None = None,
    ) -> WeeklyPlan:
        if week_start.weekday() != 0:
            raise ValueError("周计划开始日期必须是周一")
        profile_record = self._session.get(CareerProfileRecord, user_id)
        if not profile_record:
            raise ValueError("请先确认求职画像")
        profile = self._profile(profile_record)
        self._validate_items(
            user_id=user_id, profile=profile, week_start=week_start, items=items
        )
        now = datetime.now(UTC)
        current = self._session.scalar(
            select(WeeklyPlanRecord).where(
                WeeklyPlanRecord.user_id == user_id,
                WeeklyPlanRecord.week_start == week_start,
            )
        )
        draft: WeeklyPlanDraft | None = None
        draft_record: CareerPlanDraftRecord | None = None
        if draft_id:
            draft_record = self._session.scalar(
                select(CareerPlanDraftRecord).where(
                    CareerPlanDraftRecord.id == draft_id,
                    CareerPlanDraftRecord.user_id == user_id,
                )
            )
            if not draft_record or self._is_expired(draft_record.expires_at, now):
                raise ValueError("AI 规划草稿已过期，请重新生成")
            draft = WeeklyPlanDraft.model_validate(draft_record.payload)
            if draft.week_start != week_start:
                raise ValueError("规划草稿与所选周不一致")
        elif not current:
            raise ValueError("新周计划必须先生成或确认一份规划草稿")

        if not current:
            current = WeeklyPlanRecord(
                id=uuid4(),
                user_id=user_id,
                week_start=week_start,
                created_at=now,
                confirmed_at=now,
                updated_at=now,
            )
            self._session.add(current)
        current.goal = goal
        current.status = status
        current.updated_at = now
        if draft:
            current.basis = draft.basis.model_dump(mode="json")
            current.model = draft.model
            current.prompt_version = draft.prompt_version
            current.skill_version = draft.skill_version
        current.items.clear()
        self._session.flush()
        current.items.extend(
            [self._item_record(current.id, item, now=now) for item in items]
        )
        if draft_record:
            self._session.delete(draft_record)
        self._session.commit()
        self._session.refresh(current)
        return self._plan(current)

    def update_item_status(
        self, *, user_id: UUID, plan_id: UUID, item_id: UUID, status: str
    ) -> WeeklyPlanItem:
        if status not in {"pending", "in_progress", "completed", "skipped"}:
            raise ValueError("计划事项状态不正确")
        record = self._owned_item(user_id=user_id, plan_id=plan_id, item_id=item_id)
        now = datetime.now(UTC)
        record.status = status
        record.completed_at = now if status == "completed" else None
        record.updated_at = now
        self._session.flush()
        plan = self._session.get(WeeklyPlanRecord, plan_id)
        if plan:
            plan.status = (
                "completed"
                if plan.items
                and all(item.status in {"completed", "skipped"} for item in plan.items)
                else "active"
            )
            plan.updated_at = now
        self._session.commit()
        self._session.refresh(record)
        return self._item(record)

    def delete_weekly_plan(self, *, user_id: UUID, plan_id: UUID) -> None:
        record = self._session.scalar(
            select(WeeklyPlanRecord).where(
                WeeklyPlanRecord.id == plan_id,
                WeeklyPlanRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到这份周计划")
        self._session.delete(record)
        self._session.commit()

    def _proposal_items(
        self,
        *,
        proposal: CareerPlanAgentOutput,
        week_start: date,
        options: list[CareerQuestionOption],
    ) -> list[WeeklyPlanItem]:
        option_map = {item.id: item for item in options}
        result: list[WeeklyPlanItem] = []
        used_question_ids: set[UUID] = set()
        for position, item in enumerate(proposal.items):
            selected_question_id = item.question_id
            option = option_map.get(selected_question_id) if selected_question_id else None
            if item.question_id and not option:
                raise DeepSeekAgentError("规划结果引用了未授权题目")
            task_type = item.task_type
            coaching_mode = item.coaching_mode
            exercise_type = item.exercise_type
            difficulty = item.difficulty
            title = item.title
            reason = item.reason
            completion_criteria = item.completion_criteria
            if selected_question_id and selected_question_id in used_question_ids:
                option = next(
                    (
                        candidate
                        for candidate in options
                        if candidate.id not in used_question_ids
                    ),
                    None,
                )
                if option:
                    selected_question_id = option.id
                    reason = f"{reason} 已替换为另一道相关题，避免同一周重复安排。"
                else:
                    selected_question_id = None
                    task_type = "structured_expression"
                    coaching_mode = "structured_expression"
                    exercise_type = "prep_pitch"
                    difficulty = "guided"
                    title = "复盘本周回答并提炼表达模板"
                    reason = "可用题目不足，改为通用表达复盘，避免同一周重复安排同一道题。"
                    completion_criteria = "选择本周一次回答，整理为 PREP 模板并完成一次 90 秒复述。"
            if option:
                title = option.title
                if task_type == "structured_expression":
                    if option.framework not in {"star", "prep"}:
                        task_type = "question_review"
                        coaching_mode = None
                        exercise_type = None
                        difficulty = None
                    else:
                        coaching_mode = "structured_expression"
                        exercise_type = (
                            "star_story" if option.framework == "star" else "prep_pitch"
                        )
                        difficulty = difficulty or "guided"
                used_question_ids.add(option.id)
            if task_type == "question_review":
                question_target = item.question_count or self._question_target(
                    item.estimated_minutes
                )
                if not title.startswith("精练 "):
                    title = f"精练 {question_target} 道 · {title}"[:200]
                if "精练" not in completion_criteria:
                    completion_criteria = (
                        f"精练 {question_target} 道同主题题目，并完成口头复述；"
                        f"{completion_criteria}"
                    )[:500]
            result.append(
                WeeklyPlanItem(
                    id=uuid4(),
                    scheduled_date=week_start + timedelta(days=item.day_index),
                    time_slot=item.time_slot,  # type: ignore[arg-type]
                    estimated_minutes=item.estimated_minutes,
                    task_type=task_type,  # type: ignore[arg-type]
                    title=title,
                    reason=reason,
                    completion_criteria=completion_criteria,
                    status="pending",
                    origin="ai",
                    question_id=selected_question_id,
                    question_slug=option.slug if option else None,
                    coaching_mode=coaching_mode,  # type: ignore[arg-type]
                    exercise_type=exercise_type,
                    difficulty=difficulty,  # type: ignore[arg-type]
                    position=position,
                )
            )
        return result

    @staticmethod
    def _apply_explicit_day_move(
        *, items: list[WeeklyPlanItem], instruction: str, week_start: date
    ) -> list[WeeklyPlanItem]:
        if not instruction:
            return items
        match = re.search(
            r"(周[一二三四五六日天]).{0,8}(?:移到|改到|挪到|调整到).{0,4}(周[一二三四五六日天])",
            instruction,
        )
        if not match:
            return items
        day_index = {
            "周一": 0,
            "周二": 1,
            "周三": 2,
            "周四": 3,
            "周五": 4,
            "周六": 5,
            "周日": 6,
            "周天": 6,
        }
        source_date = week_start + timedelta(days=day_index[match.group(1)])
        target_date = week_start + timedelta(days=day_index[match.group(2)])
        return [
            item.model_copy(update={"scheduled_date": target_date})
            if item.scheduled_date == source_date
            else item
            for item in items
        ]

    @staticmethod
    def _training_mix(weekly_hours: int) -> dict[str, object]:
        mock_count = 0 if weekly_hours < 3 else 1 if weekly_hours < 7 else 2
        question_sessions = 1 if weekly_hours <= 2 else 2 if weekly_hours < 7 else 3
        return {
            "题目精练": (
                f"安排 {question_sessions} 次，每次 2 至 3 道同主题题目，"
                "每道只保留核心结论、关键追问和一次口头复述。"
            ),
            "结构化输出": "至少 1 次同题两答或 PREP/STAR 限时表达，必须有复盘标准。",
            "模拟面试": (
                "本周时间不足 3 小时时不安排完整模拟，改为限时追问；"
                if mock_count == 0
                else f"至少安排 {mock_count} 场，每场 45 至 90 分钟，含复盘。"
            ),
            "简历与投递": "合计不超过周时间的 15%，不能替代题目训练、表达训练或模拟面试。",
        }

    @staticmethod
    def _question_target(estimated_minutes: int) -> int:
        return 2 if estimated_minutes <= 45 else 3

    def _validate_items(
        self,
        *,
        user_id: UUID,
        profile: CareerProfile,
        week_start: date,
        items: list[WeeklyPlanItem],
    ) -> None:
        if not 1 <= len(items) <= 20:
            raise ValueError("周计划必须包含 1 至 20 项任务")
        allowed_dates = {week_start + timedelta(days=index) for index in range(7)}
        allowed_weekdays = set(profile.available_weekdays)
        if any(item.scheduled_date not in allowed_dates for item in items):
            raise ValueError("计划事项必须安排在当前周")
        if any(item.scheduled_date.weekday() not in allowed_weekdays for item in items):
            raise ValueError("计划事项安排在了不可训练的星期")
        if sum(item.estimated_minutes for item in items) > profile.weekly_hours * 60:
            raise ValueError("计划总时长超过每周可投入时间")
        if any(count > 2 for count in Counter(item.scheduled_date for item in items).values()):
            raise ValueError("每天最多安排两项训练")
        question_ids = [item.question_id for item in items if item.question_id]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("同一周不能重复安排同一道题")
        if question_ids:
            allowed = set(
                self._session.scalars(
                    select(QuestionRecord.id).where(
                        QuestionRecord.id.in_(question_ids),
                        or_(
                            QuestionRecord.published.is_(True),
                            QuestionRecord.owner_user_id == user_id,
                        ),
                    )
                ).all()
            )
            if allowed != set(question_ids):
                raise ValueError("计划包含无权访问的题目")

    def _question_options(
        self,
        *,
        user_id: UUID,
        limit: int,
        target_role: str = "",
        evidence_focus: str | None = None,
    ) -> list[CareerQuestionOption]:
        questions = self._session.scalars(
            select(QuestionRecord)
            .where(
                or_(
                    QuestionRecord.published.is_(True),
                    QuestionRecord.owner_user_id == user_id,
                )
            )
            .options(selectinload(QuestionRecord.topics))
        ).all()
        progress = {
            item.question_id: item
            for item in self._session.scalars(
                select(UserQuestionProgressRecord).where(
                    UserQuestionProgressRecord.user_id == user_id
                )
            ).all()
        }
        now = datetime.now(UTC)
        options: list[CareerQuestionOption] = []
        for item in questions:
            progress_record = progress.get(item.id)
            options.append(CareerQuestionOption(
                id=item.id,
                slug=item.slug,
                title=item.title,
                difficulty=item.difficulty,
                framework=item.framework,
                topics=[topic.name for topic in item.topics],
                source_document_name=item.source_document_name,
                review_due=bool(
                    progress_record
                    and progress_record.review_due_at
                    and progress_record.review_due_at <= now
                ),
                owned=item.owner_user_id == user_id,
            ))
        options.sort(
            key=lambda item: (
                not item.review_due,
                not item.owned,
                -self._question_relevance(
                    item, target_role=target_role, evidence_focus=evidence_focus
                ),
                item.framework not in {"star", "prep"},
                item.title,
            )
        )
        return options[:limit]

    @staticmethod
    def _question_relevance(
        item: CareerQuestionOption, *, target_role: str, evidence_focus: str | None
    ) -> int:
        haystack = f"{item.title} {' '.join(item.topics)}".casefold()
        role_terms = {
            term
            for term in target_role.casefold().replace("工程师", "").replace("开发", " ").split()
            if len(term) >= 2
        }
        focus_terms = {
            term
            for term in (evidence_focus or "")
            .casefold()
            .replace("，", " ")
            .replace("。", " ")
            .split()
            if len(term) >= 2
        }
        return sum(term in haystack for term in role_terms) * 2 + sum(
            term in haystack for term in focus_terms
        )

    @staticmethod
    def _is_expired(expires_at: datetime, now: datetime) -> bool:
        normalized = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        return normalized <= now

    def _owned_item(
        self, *, user_id: UUID, plan_id: UUID, item_id: UUID
    ) -> WeeklyPlanItemRecord:
        record = self._session.scalar(
            select(WeeklyPlanItemRecord)
            .join(WeeklyPlanRecord, WeeklyPlanRecord.id == WeeklyPlanItemRecord.plan_id)
            .where(
                WeeklyPlanItemRecord.id == item_id,
                WeeklyPlanItemRecord.plan_id == plan_id,
                WeeklyPlanRecord.user_id == user_id,
            )
        )
        if not record:
            raise LookupError("找不到这项训练计划")
        return record

    @staticmethod
    def _profile(record: CareerProfileRecord | None) -> CareerProfile:
        if not record:
            return CareerProfile()
        return CareerProfile(
            target_role=record.target_role,
            target_level=record.target_level,
            target_companies=list(record.target_companies),
            preferred_cities=list(record.preferred_cities),
            weekly_hours=record.weekly_hours,
            available_weekdays=list(record.available_weekdays),
            preferred_time_slot=record.preferred_time_slot,  # type: ignore[arg-type]
            constraints=record.constraints,
            confirmed_at=record.confirmed_at,
            updated_at=record.updated_at,
        )

    def _item(self, record: WeeklyPlanItemRecord) -> WeeklyPlanItem:
        return WeeklyPlanItem(
            id=record.id,
            plan_id=record.plan_id,
            scheduled_date=record.scheduled_date,
            time_slot=record.time_slot,  # type: ignore[arg-type]
            scheduled_time=record.scheduled_time,
            estimated_minutes=record.estimated_minutes,
            task_type=record.task_type,  # type: ignore[arg-type]
            title=record.title,
            reason=record.reason,
            completion_criteria=record.completion_criteria,
            status=record.status,  # type: ignore[arg-type]
            origin=record.origin,  # type: ignore[arg-type]
            question_id=record.question_id,
            question_slug=(
                self._session.scalar(
                    select(QuestionRecord.slug).where(QuestionRecord.id == record.question_id)
                )
                if record.question_id
                else None
            ),
            coaching_mode=record.coaching_mode,  # type: ignore[arg-type]
            exercise_type=record.exercise_type,
            difficulty=record.difficulty,  # type: ignore[arg-type]
            position=record.position,
            completed_at=record.completed_at,
        )

    @staticmethod
    def _item_record(
        plan_id: UUID, item: WeeklyPlanItem, *, now: datetime
    ) -> WeeklyPlanItemRecord:
        return WeeklyPlanItemRecord(
            id=item.id,
            plan_id=plan_id,
            scheduled_date=item.scheduled_date,
            time_slot=item.time_slot,
            scheduled_time=item.scheduled_time,
            estimated_minutes=item.estimated_minutes,
            task_type=item.task_type,
            title=item.title,
            reason=item.reason,
            completion_criteria=item.completion_criteria,
            status=item.status,
            origin=item.origin,
            question_id=item.question_id,
            coaching_mode=item.coaching_mode,
            exercise_type=item.exercise_type,
            difficulty=item.difficulty,
            position=item.position,
            completed_at=item.completed_at,
            created_at=now,
            updated_at=now,
        )

    def _plan(self, record: WeeklyPlanRecord) -> WeeklyPlan:
        return WeeklyPlan(
            id=record.id,
            week_start=record.week_start,
            goal=record.goal,
            items=[self._item(item) for item in record.items],
            status=record.status,  # type: ignore[arg-type]
            basis=PlanningBasis.model_validate(record.basis or {
                "profile_confirmed": True,
                "question_count": 0,
                "owned_question_count": 0,
                "due_question_count": 0,
                "recent_training_count": 0,
                "evidence_focus": None,
            }),
            model=record.model,
            prompt_version=record.prompt_version,
            skill_version=record.skill_version,
            confirmed_at=record.confirmed_at,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

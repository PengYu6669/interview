/* Hallmark · pre-emit critique: P5 H5 E4 S4 R5 V4
 * macrostructure: single-protagonist coach lesson · theme: studied-DNA (paper/pine/room from design.md)
 * dark only on lesson card · states: 0 unconfigured · 1 baseline · 2 recommended
 */
"use client";

import {
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  Check,
  CheckCircle2,
  Clock3,
  FileText,
  ListTree,
  LoaderCircle,
  MessageSquareText,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { AbilityProfileData, abilityProfileSchema } from "@/lib/ability-profile";
import { type WeeklyPlanItem, weeklyPlanItemSchema } from "@/lib/career";
import { cn } from "@/lib/cn";
import { COACHING_MODE_LABELS, CoachingSummary, coachingSummarySchema } from "@/lib/coaching";
import { QUESTION_COACHING_SELECTION_KEY } from "@/lib/questions";
import { prepareInterviewRetraining } from "@/lib/retraining";
import { TrainingDraftSummary, trainingDraftSummarySchema } from "@/lib/training-draft";

const modes = [
  {
    href: "/setup",
    title: "模拟面试",
    description: "完整流程与语音实战",
    icon: MessageSquareText,
    tone: "pine",
  },
  {
    href: "/training/new?mode=structured_expression",
    title: "结构化表达",
    description: "结论、职责与结果",
    icon: ListTree,
    tone: "indigo",
  },
  {
    href: "/training/new?mode=business_sense",
    title: "业务 Sense",
    description: "目标、指标与取舍",
    icon: BriefcaseBusiness,
    tone: "amber",
  },
] as const;

const modeTone = {
  pine: "bg-[hsl(var(--pine)/10%)] text-[var(--pine-color)]",
  indigo: "bg-[hsl(var(--indigo-mode)/10%)] text-[var(--indigo-mode-color)]",
  amber: "bg-[hsl(var(--amber-mode)/11%)] text-[var(--amber-mode-color)]",
} as const;

type HubPhase = "loading" | "unconfigured" | "baseline" | "recommended";

type TrailStep = {
  key: string;
  label: string;
  status: "done" | "active" | "pending";
};

function localDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function progressFor(status: CoachingSummary["status"]) {
  if (status === "completed") return 100;
  if (status === "active") return 58;
  return 18;
}

function coachNoteFor(item: CoachingSummary) {
  if (item.status === "active" && item.current_question) {
    return `我们停在「${item.current_question.slice(0, 28)}${item.current_question.length > 28 ? "…" : ""}」——续上即可。`;
  }
  if (item.status === "completed") {
    return "上一场已完成。回看证据后，我们再决定下一步。";
  }
  return "任务已备好，还没开口。今天可以从这里开始。";
}

function difficultyLabel(value: string | undefined) {
  if (value === "guided") return "有骨架";
  if (value === "assisted") return "关键词提示";
  if (value === "pressure") return "限时脱稿";
  return "标准节奏";
}

export function TrainingHub() {
  const router = useRouter();
  const [recent, setRecent] = useState<CoachingSummary[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(true);
  const [profile, setProfile] = useState<AbilityProfileData | null>(null);
  const [today, setToday] = useState<WeeklyPlanItem[]>([]);
  const [drafts, setDrafts] = useState<TrainingDraftSummary[]>([]);
  const [contextLoading, setContextLoading] = useState(true);
  const [contextError, setContextError] = useState("");
  const [startingRecommendation, setStartingRecommendation] = useState(false);
  const [recommendationError, setRecommendationError] = useState("");
  const [trailTick, setTrailTick] = useState(0);

  useEffect(() => {
    let mounted = true;
    void fetch("/api/coaching-sessions", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const parsed = coachingSummarySchema.safeParse(await response.json());
        if (mounted && parsed.success) setRecent(parsed.data);
      })
      .finally(() => {
        if (mounted) setLoadingRecent(false);
      });

    void Promise.all([
      fetch("/api/profile", { cache: "no-store" }),
      fetch(`/api/career/today?date=${localDate()}`, { cache: "no-store" }),
      fetch("/api/drafts", { cache: "no-store" }),
    ])
      .then(async ([profileResponse, todayResponse, draftsResponse]) => {
        const profilePayload: unknown = await profileResponse.json();
        const todayPayload: unknown = await todayResponse.json();
        const draftsPayload: unknown = draftsResponse.ok ? await draftsResponse.json() : [];
        const parsedProfile = profileResponse.ok ? abilityProfileSchema.safeParse(profilePayload) : null;
        const parsedToday = todayResponse.ok ? weeklyPlanItemSchema.array().safeParse(todayPayload) : null;
        const parsedDrafts = trainingDraftSummarySchema.array().safeParse(draftsPayload);
        if (!mounted) return;
        if (parsedProfile?.success) setProfile(parsedProfile.data);
        else setContextError("能力画像暂时无法读取，我会先按可见材料给你安排。");
        if (parsedToday?.success) setToday(parsedToday.data);
        if (parsedDrafts.success) setDrafts(parsedDrafts.data);
      })
      .catch(() => {
        if (mounted) setContextError("今日上下文暂时无法完整读取，请稍后刷新。");
      })
      .finally(() => {
        if (mounted) setContextLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!contextLoading && !loadingRecent) return;
    const timer = window.setInterval(() => setTrailTick((value) => value + 1), 900);
    return () => window.clearInterval(timer);
  }, [contextLoading, loadingRecent]);

  async function startPlannedItem(item: WeeklyPlanItem) {
    if (item.task_type === "question_review" && item.question_id) {
      if (item.plan_id && item.status === "pending") {
        const response = await fetch(
          `/api/career/weekly-plan/${encodeURIComponent(item.plan_id)}/items/${encodeURIComponent(item.id)}`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "in_progress" }),
          },
        );
        if (!response.ok) {
          setRecommendationError("今日任务暂时无法同步，请稍后重试");
          return;
        }
      }
      const query = item.plan_id ? `?plan=${item.plan_id}&planItem=${item.id}` : "";
      router.push(item.question_slug ? `/questions/${item.question_slug}${query}` : "/questions");
      return;
    }

    if (item.coaching_mode) {
      if (item.question_id) {
        const framework = item.exercise_type === "prep_pitch" ? "prep" : "star";
        sessionStorage.setItem(
          QUESTION_COACHING_SELECTION_KEY,
          JSON.stringify({ questions: [{ id: item.question_id, title: item.title, framework }] }),
        );
      }
      const query = new URLSearchParams({
        mode: item.coaching_mode,
        difficulty: item.difficulty ?? "guided",
        focus: item.completion_criteria,
        planItem: item.id,
      });
      router.push(`/training/new?${query.toString()}`);
      return;
    }

    router.push(item.task_type === "mock_interview" ? `/setup?planItem=${item.id}` : "/history?view=plan");
  }

  const latestDraft = drafts[0] ?? null;
  const primaryTask = today.find((item) => item.status !== "completed" && item.status !== "skipped");
  const remainingTasks = today.filter((item) => item.id !== primaryTask?.id);
  const coaching = profile?.coaching;
  const profileSourceSessionId = profile?.kline.at(-1)?.session_id;
  const hasHistory = Boolean(
    recent.length
    || (profile?.report_count ?? 0) > 0
    || (coaching?.session_count ?? 0) > 0
    || primaryTask,
  );
  const isConfigured = Boolean(
    latestDraft?.target_role?.trim()
    || latestDraft?.resume_filename?.trim()
    || hasHistory
    || (profile?.report_count ?? 0) > 0,
  );

  const phase: HubPhase = contextLoading || loadingRecent
    ? "loading"
    : !isConfigured
      ? "unconfigured"
      : hasHistory
        ? "recommended"
        : "baseline";

  const nextTrainingHref = coaching?.next_mode
    ? `/training/new?mode=${coaching.next_mode}&difficulty=${coaching.next_difficulty}&focus=${encodeURIComponent(coaching.next_focus ?? "")}`
    : "/setup";

  const primaryTitle =
    phase === "unconfigured"
      ? "第 0 课 · 让我先认识你"
      : phase === "baseline"
        ? "先完成一场基线模拟面试"
        : primaryTask?.title
          ?? profile?.next_training
          ?? coaching?.next_focus
          ?? "完成一场基于真实经历的模拟面试";

  const primaryReason =
    phase === "unconfigured"
      ? "还没有岗位与材料时，我会把准备拆成三步：目标岗位 → 上传材料 → 校正我对你的理解。不会让你直接掉进冷启动面试。"
      : phase === "baseline"
        ? "材料已经够我开场了，但还没有你的表现证据。先完成一场基线面试，后面的推荐才会站得住。"
        : primaryTask?.reason
          ?? (profile?.next_training
            ? `我对照了你最近的证据报告，建议继续验证：${profile.next_training}`
            : coaching?.next_focus
              ? `专项训练画像指向：${coaching.next_focus}`
              : "我会用已有计划与证据，只推进今天最关键的一步。");

  const primaryMeta =
    phase === "unconfigured"
      ? "约 8 分钟 · 三步建档"
      : phase === "baseline"
        ? "约 30 分钟 · 建立第一份能力证据"
        : primaryTask
          ? `${primaryTask.estimated_minutes} 分钟 · ${primaryTask.completion_criteria}`
          : profile?.next_training
            ? `30 分钟 · 基于 ${profile.report_count} 份有效报告`
            : coaching?.next_mode
              ? `10 分钟 · ${coaching.current_streak_days} 天连续 · ${difficultyLabel(coaching.next_difficulty)}`
              : "约 30 分钟 · 今日一课";

  const sourceBadge =
    phase === "unconfigured"
      ? "开场引导"
      : phase === "baseline"
        ? "建立训练基线"
        : primaryTask
          ? "来自本周计划"
          : profile?.next_training
            ? "来自最近证据报告"
            : coaching?.next_mode
              ? "来自专项训练画像"
              : "今日一课";

  const coachNote =
    phase === "loading"
      ? "我先对照计划、弱项与未完成草稿，再给你唯一的下一步。"
      : phase === "unconfigured"
        ? "先别急着进考场。把目标与材料交代清楚，后面的追问才像真人面试官。"
        : phase === "baseline"
          ? "基线不是考核，是我们共同的参照点。答得不完整也没关系，证据会留下来。"
          : primaryTask
            ? "今天只推进这一课。做完再决定要不要加练。"
            : "我把次要入口都收弱了——先完成这一课。";

  const trailSteps = useMemo<TrailStep[]>(() => {
    if (phase === "loading") {
      const activeIndex = trailTick % 3;
      return [
        { key: "plan", label: "对照求职计划", status: activeIndex === 0 ? "active" : activeIndex > 0 ? "done" : "pending" },
        { key: "weak", label: "检查上周弱项", status: activeIndex === 1 ? "active" : activeIndex > 1 ? "done" : "pending" },
        { key: "task", label: "生成今日任务", status: activeIndex === 2 ? "active" : "pending" },
      ];
    }
    if (phase === "unconfigured") {
      const roleReady = Boolean(latestDraft?.target_role?.trim());
      const materialReady = Boolean(latestDraft?.resume_filename?.trim());
      return [
        { key: "role", label: "目标岗位", status: roleReady ? "done" : "active" },
        { key: "material", label: "上传材料", status: materialReady ? "done" : roleReady ? "active" : "pending" },
        { key: "confirm", label: "校正理解", status: materialReady ? "active" : "pending" },
      ];
    }
    if (phase === "baseline") {
      return [
        { key: "materials", label: "材料已就绪", status: "done" },
        { key: "baseline", label: "等待基线面试", status: "active" },
        { key: "evidence", label: "形成第一份证据", status: "pending" },
      ];
    }
    return [
      { key: "plan", label: "计划已读取", status: "done" },
      { key: "evidence", label: "证据已对齐", status: "done" },
      { key: "today", label: "今日任务已确定", status: "active" },
    ];
  }, [phase, trailTick, latestDraft]);

  const primaryHref =
    phase === "unconfigured"
      ? "/setup"
      : phase === "baseline"
        ? "/setup"
        : primaryTask
          ? null
          : profile?.next_training && profileSourceSessionId
            ? null
            : nextTrainingHref;

  const primaryLabel =
    phase === "unconfigured"
      ? "开始第 0 课"
      : phase === "baseline"
        ? "开始基线面试"
        : primaryTask
          ? "开始今日训练"
          : profile?.next_training && profileSourceSessionId
            ? startingRecommendation
              ? "正在准备来源证据"
              : "开始弱项复训"
            : "开始今日训练";

  async function startProfileRecommendation() {
    if (!profile?.next_training || !profileSourceSessionId) return;
    setStartingRecommendation(true);
    setRecommendationError("");
    try {
      await prepareInterviewRetraining({
        sourceSessionId: profileSourceSessionId,
        focus: profile.next_training,
      });
      router.push("/setup");
    } catch (caught) {
      setRecommendationError(caught instanceof Error ? caught.message : "暂时无法准备弱项复训");
    } finally {
      setStartingRecommendation(false);
    }
  }

  async function onPrimaryClick() {
    if (primaryTask) {
      await startPlannedItem(primaryTask);
      return;
    }
    if (phase === "recommended" && profile?.next_training && profileSourceSessionId) {
      await startProfileRecommendation();
    }
  }

  const showSessionRail = phase === "recommended" && recent.length > 0;

  return (
    <main className="mx-auto w-[min(72rem,calc(100%-3rem))] pb-20 pt-12 max-[700px]:w-[calc(100%-1.75rem)] max-[700px]:pt-8">
      <header className="mb-6 max-w-[40rem]">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--pine-color)]">AI 面试教练</p>
        <h1 className="mt-2 text-[clamp(1.75rem,3.4vw,2.35rem)] font-extrabold leading-tight text-[var(--ink)]">
          今天只推进一件事
        </h1>
      </header>

      <section
        className="relative isolate overflow-hidden rounded-[1.15rem] bg-[linear-gradient(145deg,var(--pine-deep-color)_0%,var(--room-color)_58%,hsl(150_14%_8%)_100%)] p-7 text-[var(--room-text)] shadow-[var(--shadow-lift)] max-[700px]:p-5"
        aria-label="今日一课"
      >
        <div
          className="coach-breathe pointer-events-none absolute -right-16 -top-20 size-[18rem] rounded-full bg-[radial-gradient(circle,hsl(var(--pine-bright)/28%),transparent_68%)]"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-24 left-10 size-[14rem] rounded-full bg-[radial-gradient(circle,hsl(var(--pine)/18%),transparent_70%)] opacity-70"
          aria-hidden
        />

        <div className="relative z-[1] grid gap-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex min-h-7 items-center rounded-full border border-white/25 bg-white/10 px-2.5 text-xs font-semibold text-white">
              {sourceBadge}
            </span>
            <span className="inline-flex min-h-7 items-center gap-1.5 rounded-full border border-white/15 bg-black/15 px-2.5 text-xs text-white/80">
              <Bot size={13} />
              教练在场
            </span>
          </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <div className="min-w-0">
              <h2 className="max-w-[42rem] text-[clamp(1.35rem,2.6vw,1.85rem)] font-extrabold leading-snug text-white">
                {primaryTitle}
              </h2>
              <p className="mt-2 max-w-[40rem] text-sm leading-relaxed text-white/85">{primaryReason}</p>
              <p className="mt-3 max-w-[38rem] border-l-2 border-[var(--room-glow-color)] pl-3 text-[13px] leading-relaxed text-white/80">
                {coachNote}
              </p>
              <small className="mt-3 flex items-center gap-1.5 text-[13px] tabular-nums text-white/75">
                <Clock3 size={13} />
                {primaryMeta}
              </small>
            </div>

            {phase !== "loading" && (
              primaryHref ? (
                <Button className="w-full shrink-0 max-[700px]:mt-1 lg:w-auto" variant="onDark" size="lg" asChild>
                  <Link href={primaryHref}>
                    {primaryLabel}
                    <ArrowRight size={16} />
                  </Link>
                </Button>
              ) : (
                <Button
                  className="w-full shrink-0 max-[700px]:mt-1 lg:w-auto"
                  variant="onDark"
                  size="lg"
                  type="button"
                  disabled={startingRecommendation}
                  onClick={() => void onPrimaryClick()}
                >
                  {startingRecommendation && <LoaderCircle className="spin" size={15} />}
                  {primaryLabel}
                  <ArrowRight size={16} />
                </Button>
              )
            )}
          </div>

          <ol className="grid gap-2 border-t border-white/15 pt-4 sm:grid-cols-3" aria-label="教练准备进度">
            {trailSteps.map((step, index) => (
              <li key={step.key} className="flex items-center gap-2.5">
                <span
                  className={cn(
                    "coach-trail-dot grid size-6 shrink-0 place-items-center rounded-full border text-[11px] font-bold",
                    step.status === "done" && "border-[var(--room-glow-color)] bg-[hsl(var(--pine-bright)/20%)] text-[var(--room-glow-color)]",
                    step.status === "active" && "is-active border-[var(--room-glow-color)] bg-[var(--room-glow-color)] text-[var(--pine-deep-color)]",
                    step.status === "pending" && "border-white/25 bg-white/5 text-white/55",
                  )}
                >
                  {step.status === "done" ? <Check size={12} /> : index + 1}
                </span>
                <span className={cn("text-xs font-semibold", step.status === "pending" ? "text-white/55" : "text-white")}>
                  {step.label}
                </span>
                {index < trailSteps.length - 1 && (
                  <span
                    className={cn(
                      "coach-trail-line ml-auto hidden h-px w-8 bg-white/25 sm:block",
                      step.status !== "pending" && "is-active bg-[var(--room-glow-color)]",
                    )}
                    aria-hidden
                  />
                )}
              </li>
            ))}
          </ol>

          {phase === "unconfigured" && (
            <div className="grid gap-2 rounded-[0.9rem] border border-white/12 bg-black/20 p-3 sm:grid-cols-3">
              {[
                { title: "1. 目标岗位", text: latestDraft?.target_role || "还没填写", href: "/setup", done: Boolean(latestDraft?.target_role?.trim()) },
                { title: "2. 上传材料", text: latestDraft?.resume_filename || "简历 / JD 待上传", href: "/setup", done: Boolean(latestDraft?.resume_filename?.trim()) },
                { title: "3. 校正理解", text: "我会复述你的经历，由你确认", href: "/setup", done: false },
              ].map((step) => (
                <Link
                  key={step.title}
                  href={step.href}
                  className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 transition-colors hover:bg-white/10"
                >
                  <span className="flex items-center justify-between gap-2 text-xs font-bold text-white">
                    {step.title}
                    {step.done ? <CheckCircle2 size={14} className="text-[var(--room-glow-color)]" /> : <Target size={14} className="text-white/50" />}
                  </span>
                  <span className="mt-1 block text-xs leading-relaxed text-white/70">{step.text}</span>
                </Link>
              ))}
            </div>
          )}

          {(recommendationError || contextError) && (
            <p className="border-l-2 border-[hsl(var(--vermilion))] pl-2.5 text-sm text-[#ffb4ac]" role="alert">
              {recommendationError || contextError}
            </p>
          )}

          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/12 pt-3 text-xs text-white/70">
            <span>推荐依据可核对；我不会偷偷改你的目标或记录。</span>
            <Button variant="linkOnDark" size="sm" asChild>
              <Link href="/history?view=plan">
                查看本周计划
                <ArrowRight size={13} />
              </Link>
            </Button>
          </footer>
        </div>
      </section>

      {phase === "loading" && (
        <p className="mt-4 flex items-center gap-2 text-sm text-[var(--muted)]" aria-live="polite">
          <LoaderCircle className="spin" size={15} />
          正在对照计划与证据，准备你的今日一课…
        </p>
      )}

      {showSessionRail && (
        <section className="mt-8" aria-label="继续上次训练">
          <div className="mb-3 flex items-end justify-between gap-3">
            <h2 className="text-lg font-bold text-[var(--ink)]">继续上次训练</h2>
            <span className="text-xs text-[var(--muted)]">像会话一样续上，而不是表格行</span>
          </div>
          <div className="grid gap-2">
            {recent.slice(0, 4).map((item) => {
              const progress = progressFor(item.status);
              return (
                <Link
                  key={item.id}
                  href={`/training/${item.id}`}
                  className="group grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-[1rem] border border-[var(--line)] bg-[var(--surface)] px-3.5 py-3 shadow-[var(--shadow-soft)] transition-[transform,box-shadow,border-color] duration-150 hover:-translate-y-px hover:border-[hsl(var(--pine)/35%)] hover:shadow-[var(--shadow-lift)] max-[620px]:grid-cols-[minmax(0,1fr)_auto]"
                >
                  <span className="grid size-10 place-items-center rounded-full bg-[hsl(var(--pine)/10%)] text-[var(--pine-color)] max-[620px]:hidden">
                    <MessageSquareText size={17} />
                  </span>
                  <span className="min-w-0">
                    <strong className="block truncate text-[15px] text-[var(--ink)]">{item.title}</strong>
                    <span className="mt-0.5 block truncate text-xs text-[var(--muted)]">
                      {COACHING_MODE_LABELS[item.mode]} · {item.target_role} · {item.turn_count} 轮
                    </span>
                    <span className="mt-1 block truncate text-xs text-[var(--ink-soft-color)]">{coachNoteFor(item)}</span>
                    <span className="mt-2 block h-1 overflow-hidden rounded-full bg-[var(--surface-muted)]">
                      <i
                        className="block h-full rounded-full bg-[var(--pine-color)]"
                        style={{ width: `${progress}%` }}
                        aria-hidden
                      />
                    </span>
                  </span>
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--pine-deep-color)]">
                    继续
                    <ArrowRight size={14} className="transition-transform group-hover:translate-x-0.5" />
                  </span>
                </Link>
              );
            })}
          </div>
        </section>
      )}

      {remainingTasks.length > 0 && phase === "recommended" && (
        <section className="mt-6 rounded-[1rem] border border-[var(--line)] bg-[var(--surface)] p-4 shadow-[var(--shadow-soft)]" aria-label="今日其他安排">
          <header className="mb-2 flex items-center gap-2 text-[var(--ink)]">
            <CheckCircle2 className="text-[var(--accent)]" size={16} />
            <strong className="text-sm">今日其他安排</strong>
            <span className="text-xs text-[var(--muted)]">
              {remainingTasks.filter((item) => item.status !== "completed").length} 项待完成
            </span>
          </header>
          <div className="grid gap-2">
            {remainingTasks.map((item) => (
              <article key={item.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-t border-[var(--line)] py-2.5 first:border-t-0">
                <div className="min-w-0">
                  <strong className="block truncate text-[13px]">{item.title}</strong>
                  <small className="mt-0.5 block text-xs text-[var(--muted)]">
                    {item.estimated_minutes} 分钟 · {item.completion_criteria}
                  </small>
                </div>
                {item.status !== "completed" && item.status !== "skipped" && (
                  <Button variant="secondary" size="sm" type="button" onClick={() => void startPlannedItem(item)}>
                    开始
                    <ArrowRight size={14} />
                  </Button>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="mt-10" aria-label="次级入口">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-base font-bold text-[var(--ink)]">换一种练法</h2>
            <p className="mt-1 text-xs text-[var(--muted)]">次要入口。不会盖过上面的今日一课。</p>
          </div>
          <Link
            href="/setup"
            className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--muted)] underline-offset-4 hover:text-[var(--pine-deep-color)] hover:underline"
          >
            <Sparkles size={13} />
            先体验一场演示面试
          </Link>
        </div>
        <div className="grid grid-cols-3 gap-2.5 max-[900px]:grid-cols-1">
          {modes.map(({ href, title, description, icon: Icon, tone }) => (
            <Link
              key={title}
              href={href}
              className="group grid grid-cols-[2.25rem_minmax(0,1fr)_auto] items-center gap-2.5 rounded-[0.95rem] border border-[var(--line)] bg-[var(--surface)] px-3.5 py-3 text-[var(--ink)] shadow-[var(--shadow-soft)] transition-[border-color,box-shadow] hover:border-[hsl(var(--pine)/30%)] hover:shadow-[var(--shadow-lift)]"
            >
              <span className={cn("grid size-9 place-items-center rounded-full", modeTone[tone])}>
                <Icon size={16} />
              </span>
              <span className="min-w-0">
                <strong className="block text-sm">{title}</strong>
                <span className="mt-0.5 block text-xs text-[var(--muted)]">{description}</span>
              </span>
              <ArrowRight size={15} className="text-[var(--muted)] transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--pine-color)]" />
            </Link>
          ))}
        </div>
        {latestDraft && (
          <p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--muted)]">
            <FileText size={13} />
            检测到未完成草稿：{latestDraft.target_role || "未命名岗位"}
            {latestDraft.resume_filename ? ` · ${latestDraft.resume_filename}` : ""}
            <Link href="/setup" className="ml-1 font-semibold text-[var(--pine-deep-color)] hover:underline">
              继续准备
            </Link>
          </p>
        )}
        {!showSessionRail && !loadingRecent && recent.length === 0 && phase !== "unconfigured" && (
          <p className="mt-4 text-xs text-[var(--muted)]">完成一次专项训练后，续练会话会出现在上方。</p>
        )}
      </section>
    </main>
  );
}

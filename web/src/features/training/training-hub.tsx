"use client";

import {
  ArrowRight,
  Bot,
  BriefcaseBusiness,
  CheckCircle2,
  Clock3,
  ListTree,
  LoaderCircle,
  MessageSquareText,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AbilityProfileData, abilityProfileSchema } from "@/lib/ability-profile";
import { type WeeklyPlanItem, weeklyPlanItemSchema } from "@/lib/career";
import { cn } from "@/lib/cn";
import { COACHING_MODE_LABELS, CoachingSummary, coachingSummarySchema } from "@/lib/coaching";
import { QUESTION_COACHING_SELECTION_KEY } from "@/lib/questions";
import { prepareInterviewRetraining } from "@/lib/retraining";

const modes = [
  {
    href: "/setup",
    title: "模拟面试",
    description: "完整面试流程与语音实战",
    icon: MessageSquareText,
    tone: "pine",
  },
  {
    href: "/training/new?mode=structured_expression",
    title: "结构化表达",
    description: "结论、职责、取舍与结果",
    icon: ListTree,
    tone: "indigo",
  },
  {
    href: "/training/new?mode=business_sense",
    title: "业务 Sense",
    description: "目标、指标、优先级与验证",
    icon: BriefcaseBusiness,
    tone: "amber",
  },
] as const;

const modeTone = {
  pine: {
    icon: "bg-[hsl(var(--pine)/10%)] text-[var(--pine-color)]",
    action: "bg-[hsl(var(--pine)/10%)] text-[var(--pine-color)] group-hover:bg-[var(--pine-color)] group-hover:text-white",
  },
  indigo: {
    icon: "bg-[hsl(var(--indigo-mode)/10%)] text-[var(--indigo-mode-color)]",
    action: "bg-[hsl(var(--indigo-mode)/10%)] text-[var(--indigo-mode-color)] group-hover:bg-[var(--indigo-mode-color)] group-hover:text-white",
  },
  amber: {
    icon: "bg-[hsl(var(--amber-mode)/11%)] text-[var(--amber-mode-color)]",
    action: "bg-[hsl(var(--amber-mode)/11%)] text-[var(--amber-mode-color)] group-hover:bg-[var(--amber-mode-color)] group-hover:text-white",
  },
} as const;

function localDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function statusTone(status: CoachingSummary["status"]) {
  if (status === "completed") return "success";
  if (status === "active") return "accent";
  return "neutral";
}

function statusLabel(status: CoachingSummary["status"]) {
  if (status === "completed") return "已完成";
  if (status === "active") return "进行中";
  return "待开始";
}

export function TrainingHub() {
  const router = useRouter();
  const [recent, setRecent] = useState<CoachingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<AbilityProfileData | null>(null);
  const [today, setToday] = useState<WeeklyPlanItem[]>([]);
  const [recommendationLoading, setRecommendationLoading] = useState(true);
  const [contextError, setContextError] = useState("");
  const [startingRecommendation, setStartingRecommendation] = useState(false);
  const [recommendationError, setRecommendationError] = useState("");

  useEffect(() => {
    let mounted = true;
    void fetch("/api/coaching-sessions", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return;
        const parsed = coachingSummarySchema.safeParse(await response.json());
        if (mounted && parsed.success) setRecent(parsed.data);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    void Promise.all([
      fetch("/api/profile", { cache: "no-store" }),
      fetch(`/api/career/today?date=${localDate()}`, { cache: "no-store" }),
    ])
      .then(async ([profileResponse, todayResponse]) => {
        const profilePayload: unknown = await profileResponse.json();
        const todayPayload: unknown = await todayResponse.json();
        const parsedProfile = profileResponse.ok ? abilityProfileSchema.safeParse(profilePayload) : null;
        const parsedToday = todayResponse.ok ? weeklyPlanItemSchema.array().safeParse(todayPayload) : null;
        if (!mounted) return;
        if (parsedProfile?.success) setProfile(parsedProfile.data);
        else setContextError("能力画像暂时无法读取，今日建议没有降级为基线训练。");
        if (parsedToday?.success) setToday(parsedToday.data);
      })
      .catch(() => {
        if (mounted) setContextError("训练计划与能力画像暂时无法读取，请稍后刷新页面。");
      })
      .finally(() => {
        if (mounted) setRecommendationLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

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

  const primaryTask = today.find((item) => item.status !== "completed" && item.status !== "skipped");
  const remainingTasks = today.filter((item) => item.id !== primaryTask?.id);
  const coaching = profile?.coaching;
  const profileSourceSessionId = profile?.kline.at(-1)?.session_id;
  const nextTrainingHref = coaching?.next_mode
    ? `/training/new?mode=${coaching.next_mode}&difficulty=${coaching.next_difficulty}&focus=${encodeURIComponent(coaching.next_focus ?? "")}`
    : "/setup";

  const primaryTitle =
    primaryTask?.title
    ?? profile?.next_training
    ?? coaching?.next_focus
    ?? "完成一场基于真实经历的模拟面试";

  const primaryReason =
    primaryTask?.reason
    ?? (profile?.next_training
      ? `最近一场证据报告建议继续验证：${profile.next_training}`
      : coaching?.next_focus
        ? `专项训练画像建议继续验证：${coaching.next_focus}`
        : "还没有足够的历史证据，先完成一次基线训练。");

  const primaryMeta = primaryTask
    ? `${primaryTask.estimated_minutes} 分钟 · ${primaryTask.completion_criteria}`
    : profile?.next_training
      ? `30 分钟 · 基于最近 ${profile.report_count} 份有效报告`
      : coaching?.next_mode
        ? `10 分钟 · ${coaching.current_streak_days} 天连续训练 · ${
          coaching.next_difficulty === "guided"
            ? "有骨架"
            : coaching.next_difficulty === "assisted"
              ? "关键词提示"
              : "限时脱稿"
        }`
        : "30 分钟 · 建立第一份能力证据";

  const sourceBadge = primaryTask
    ? "来自本周计划"
    : profile?.next_training
      ? "来自最近证据报告"
      : coaching?.next_mode
        ? "来自专项训练画像"
        : "建立训练基线";

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

  return (
    <main className="mx-auto w-[min(1180px,calc(100%-48px))] pb-20 pt-14 max-[700px]:w-[calc(100%-28px)] max-[700px]:pt-8">
      <header className="flex items-end justify-between gap-7 pb-6 max-[620px]:flex-col max-[620px]:items-start">
        <div>
          <p className="eyebrow">AI 面试教练</p>
          <h1 className="mt-2.5 text-[38px] font-extrabold leading-[1.18] tracking-tight text-[var(--ink)] max-[700px]:text-[29px]">
            今天只推进一个能力目标
          </h1>
          <p className="mt-2.5 max-w-[720px] text-sm leading-[1.75] text-[var(--muted)]">
            推荐来自已确认的求职计划、历史训练证据和待验证弱项；依据不足时，系统会明确从基线训练开始。
          </p>
        </div>
      </header>

      {recommendationLoading ? (
        <section
          className="mt-1 flex min-h-[154px] items-center gap-3 rounded-lg border border-[var(--line)] bg-[var(--surface)] p-6 text-[var(--accent-dark)]"
          aria-live="polite"
        >
          <LoaderCircle className="spin shrink-0" size={18} />
          <div>
            <strong className="block text-[13px]">正在汇总今日训练上下文</strong>
            <span className="mt-1 block text-xs text-[var(--muted)]">
              读取已确认计划、历史证据和待验证弱项
            </span>
          </div>
        </section>
      ) : contextError ? (
        <section
          className="mt-1 flex min-h-[154px] items-center gap-3 rounded-lg border border-[var(--line)] bg-[var(--surface)] p-6 text-[var(--accent-dark)]"
          role="alert"
        >
          <Bot className="shrink-0" size={18} />
          <div>
            <strong className="block text-[13px]">今日建议读取失败</strong>
            <span className="mt-1 block text-xs text-[var(--muted)]">{contextError}</span>
          </div>
        </section>
      ) : (
        <section
          className="relative isolate mt-1 grid min-h-[230px] grid-cols-[minmax(0,1fr)_auto] items-center gap-6 overflow-hidden rounded-lg bg-[linear-gradient(140deg,var(--pine-deep-color),var(--room-color))] p-8 text-white shadow-[var(--shadow-lift)] after:pointer-events-none after:absolute after:right-[-80px] after:top-[-120px] after:-z-10 after:size-[360px] after:rounded-full after:bg-[radial-gradient(circle,hsl(var(--pine-bright)/22%),transparent_68%)] after:content-[''] max-[700px]:min-h-0 max-[700px]:p-5 max-[620px]:grid-cols-1"
          aria-label="今日教练建议"
        >
          <div className="flex items-start gap-4 max-[620px]:gap-2.5">
            <span className="grid size-11 shrink-0 place-items-center rounded-md bg-white/10 text-[var(--room-glow-color)] shadow-[0_0_0_8px_rgb(255_255_255/0.03)]">
              <Bot size={22} />
            </span>
            <div className="min-w-0">
              <span className="inline-flex min-h-6 items-center rounded-md border border-white/30 bg-white/15 px-2 py-0.5 text-xs font-semibold text-white">
                {sourceBadge}
              </span>
              <h2 className="mt-2.5 max-w-[760px] text-[28px] font-extrabold leading-[1.3] text-white max-[700px]:text-[22px] max-[620px]:text-lg">
                {primaryTitle}
              </h2>
              <p className="mt-1.5 max-w-[760px] text-sm leading-[1.7] text-white/85">
                {primaryReason}
              </p>
              <small className="mt-3 flex items-center gap-1.5 text-[13px] text-white/80">
                <Clock3 size={13} />
                {primaryMeta}
              </small>
            </div>
          </div>

          {primaryTask ? (
            <Button className="shrink-0 max-[620px]:w-full" variant="onDark" size="lg" type="button" onClick={() => void startPlannedItem(primaryTask)}>
              开始今日训练
              <ArrowRight size={16} />
            </Button>
          ) : profile?.next_training && profileSourceSessionId ? (
            <Button
              className="shrink-0 max-[620px]:w-full"
              variant="onDark"
              size="lg"
              type="button"
              disabled={startingRecommendation}
              onClick={() => void startProfileRecommendation()}
            >
              {startingRecommendation && <LoaderCircle className="spin" size={15} />}
              {startingRecommendation ? "正在准备来源证据" : "开始弱项复训"}
              <ArrowRight size={16} />
            </Button>
          ) : (
            <Button className="shrink-0 max-[620px]:w-full" variant="onDark" asChild size="lg">
              <Link href={nextTrainingHref}>
                开始今日训练
                <ArrowRight size={16} />
              </Link>
            </Button>
          )}

          {recommendationError && (
            <p className="col-span-full border-l-2 border-[var(--danger)] pl-2.5 text-sm text-[#ffb4ac]" role="alert">
              {recommendationError}
            </p>
          )}

          <footer className="col-span-full flex items-center justify-between gap-4 border-t border-white/20 pt-3 text-xs text-white/75 max-[620px]:flex-col max-[620px]:items-start">
            <span>推荐依据可核对，不会自动修改你的求职目标或训练记录。</span>
            <Button variant="linkOnDark" size="sm" asChild>
              <Link href="/history?view=plan">
                查看本周计划
                <ArrowRight size={13} />
              </Link>
            </Button>
          </footer>
        </section>
      )}

      {remainingTasks.length > 0 && (
        <section
          className="mt-3.5 overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--surface)] text-[var(--ink)] shadow-[var(--shadow-soft)]"
          aria-label="今日其他任务"
        >
          <header className="flex min-h-14 items-center justify-between gap-3 px-4 py-2.5">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="text-[var(--accent)]" size={18} />
              <div>
                <span className="block text-xs text-[var(--muted)]">今日其他安排</span>
                <strong className="mt-0.5 block text-[13px]">
                  {remainingTasks.filter((item) => item.status !== "completed").length} 项待完成
                </strong>
              </div>
            </div>
          </header>
          <div className="border-t border-[var(--line)]">
            {remainingTasks.map((item) => (
              <article
                key={item.id}
                className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2.5 border-t border-[var(--line)] px-4 py-3 first:border-t-0 max-[620px]:grid-cols-[auto_minmax(0,1fr)]"
              >
                <span className={cn("text-[var(--muted)]", item.status === "completed" && "text-[var(--success)]")}>
                  {item.status === "completed" ? <CheckCircle2 size={15} /> : <Clock3 size={15} />}
                </span>
                <div>
                  <strong className="block text-[13px]">{item.title}</strong>
                  <small className="mt-0.5 block text-xs leading-normal text-[var(--muted)]">
                    {item.estimated_minutes} 分钟 · {item.completion_criteria}
                  </small>
                </div>
                {item.status !== "completed" && item.status !== "skipped" && (
                  <Button
                    className="max-[620px]:col-start-2 max-[620px]:justify-self-start"
                    variant="secondary"
                    size="sm"
                    type="button"
                    onClick={() => void startPlannedItem(item)}
                  >
                    开始
                    <ArrowRight size={14} />
                  </Button>
                )}
              </article>
            ))}
          </div>
        </section>
      )}

      <div className="mt-11 flex items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-[var(--ink)]">或者自主选择训练方式</h2>
        <span className="text-xs text-[var(--muted)]">不会覆盖教练推荐</span>
      </div>

      <section className="mt-3 grid grid-cols-3 gap-3.5 max-[900px]:grid-cols-1" aria-label="训练方式">
        {modes.map(({ href, title, description, icon: Icon, tone }) => (
          <Link
            key={title}
            href={href}
            className="group grid min-h-[126px] grid-cols-[38px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg border border-[var(--line)] bg-[var(--surface)] p-5 text-[var(--ink)] shadow-[var(--shadow-soft)] transition-[transform,box-shadow,border-color] duration-150 hover:-translate-y-0.5 hover:shadow-[var(--shadow-lift)] max-[900px]:min-h-[82px]"
          >
            <span className={cn("grid size-[38px] place-items-center rounded-full", modeTone[tone].icon)}>
              <Icon size={19} />
            </span>
            <div>
              <h2 className="text-[17px] font-bold">{title}</h2>
              <p className="mt-1 text-[13px] leading-snug text-[var(--muted)]">{description}</p>
            </div>
            <span className={cn("grid size-[30px] place-items-center rounded-full transition-colors", modeTone[tone].action)}>
              <ArrowRight size={16} />
            </span>
          </Link>
        ))}
      </section>

      <section className="mt-11">
        <div className="mb-3 flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold text-[var(--ink)]">继续上次训练</h2>
        </div>

        {loading ? (
          <div className="flex min-h-[116px] items-center gap-3 border-y border-[var(--line)] text-[13px] text-[var(--muted)]">
            正在读取训练记录
          </div>
        ) : recent.length ? (
          <div className="border-y border-[var(--line-strong)]">
            {recent.map((item) => (
              <Link
                key={item.id}
                href={`/training/${item.id}`}
                className="grid min-h-[84px] grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-5 border-t border-[var(--line)] px-2 py-3 first:border-t-0 transition-colors hover:bg-[hsl(var(--pine)/5%)] max-[620px]:grid-cols-[minmax(0,1fr)_auto]"
              >
                <div className="min-w-0">
                  <strong className="block text-[15px]">{item.title}</strong>
                  <span className="mt-1 block truncate text-xs text-[var(--muted)]">
                    {COACHING_MODE_LABELS[item.mode]} · {item.target_role} · {item.turn_count} 轮
                  </span>
                </div>
                <time className="text-xs text-[var(--muted)] max-[620px]:hidden">
                  {new Date(item.updated_at).toLocaleDateString("zh-CN")}
                </time>
                <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
              </Link>
            ))}
          </div>
        ) : (
          <div className="flex min-h-[116px] items-center gap-3 border-y border-[var(--line)] text-[13px] text-[var(--muted)]">
            <Sparkles size={18} />
            完成一次专项训练后，记录会出现在这里。
          </div>
        )}
      </section>
    </main>
  );
}

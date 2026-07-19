"use client";

import {
  ArrowRight,
  AudioLines,
  BriefcaseBusiness,
  CheckCircle2,
  Clock3,
  ListTree,
  LoaderCircle,
  MessageSquareText,
  Mic,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/loading-skeleton";
import { cn } from "@/lib/cn";
import { COACHING_MODE_LABELS } from "@/lib/coaching";

import { useTrainingHub, HubPhase } from "./use-training-hub";

const drillModes = [
  {
    href: "/training/new?mode=structured_expression",
    title: "结构化表达",
    description: "10 分钟短练：结论、职责、结果",
    icon: ListTree,
  },
  {
    href: "/training/new?mode=business_sense",
    title: "业务 Sense",
    description: "10 分钟短练：目标、指标、取舍",
    icon: BriefcaseBusiness,
  },
  {
    href: "/questions",
    title: "题库热身",
    description: "先理清知识点，再进语音考场",
    icon: MessageSquareText,
  },
] as const;

function heroContent(phase: HubPhase, interviewTask: ReturnType<typeof useTrainingHub>["interviewTask"], profile: ReturnType<typeof useTrainingHub>["profile"]) {
  if (phase === "unconfigured") {
    return {
      title: "上传简历和目标岗位，开始第一场模拟面试",
      body: "实时语音、追问深挖、证据复盘——不是做题，是练讲清你的项目。",
      meta: "约 8 分钟准备 · 进入语音考场",
    };
  }
  if (interviewTask) {
    return {
      title: interviewTask.title,
      body: interviewTask.reason ?? "",
      meta: `${interviewTask.estimated_minutes} 分钟 · 语音模拟面试`,
    };
  }
  return {
    title: profile?.next_training
      ? `弱项复训：${profile.next_training}`
      : "进入实时语音模拟面试",
    body: "",
    meta: "约 30 分钟 · 实时语音 · 证据化复盘",
  };
}

export function TrainingHub() {
  const {
    recent,
    profile,
    interviewTask,
    otherTasks,
    coaching,
    profileSourceSessionId,
    latestDraft,
    contextError,
    startingRecommendation,
    recommendationError,
    phase,
    activeDrill,
    startPlannedItem,
    startWeaknessInterview,
  } = useTrainingHub();

  const hero = heroContent(phase, interviewTask, profile);

  if (phase === "loading") {
    return <PageSkeleton />;
  }

  return (
    <main className="mx-auto w-[min(72rem,calc(100%-3rem))] pb-20 pt-12 max-[700px]:w-[calc(100%-1.75rem)] max-[700px]:pt-8">
      <header className="mb-6 max-w-[42rem]">
        <h1 className="text-balance text-4xl font-semibold leading-tight text-[var(--text-primary)]">
          训练中心
        </h1>
      </header>

      {/* Hero card */}
      <section
        className="relative overflow-hidden rounded-xl border border-[var(--accent)] bg-[var(--accent)] p-6 text-white"
        aria-label="实时语音模拟面试"
      >
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex min-h-7 items-center gap-1.5 rounded-full border border-white/25 bg-white/10 px-2.5 text-xs font-semibold">
                <Mic size={13} />
                实时语音考场
              </span>
              <span className="inline-flex min-h-7 items-center gap-1.5 rounded-full border border-white/15 bg-black/20 px-2.5 text-xs text-white/80">
                <AudioLines size={13} />
                摄像头 · 转写 · 追问
              </span>
            </div>
            <h2 className="mt-3 max-w-[40rem] text-balance text-2xl font-semibold leading-snug">
              {hero.title}
            </h2>
            {hero.body && (
              <p className="mt-2 max-w-[40rem] text-sm leading-relaxed text-white/85">{hero.body}</p>
            )}
            <small className="mt-3 flex items-center gap-1.5 text-[13px] tabular-nums text-white/75">
              <Clock3 size={13} />
              {hero.meta}
            </small>
            {contextError && (
              <p className="mt-3 border-l-2 border-[hsl(var(--vermilion))] pl-2.5 text-sm text-[#ffb4ac]" role="alert">
                {contextError}
              </p>
            )}
            {recommendationError && (
              <p className="mt-3 border-l-2 border-[hsl(var(--vermilion))] pl-2.5 text-sm text-[#ffb4ac]" role="alert">
                {recommendationError}
              </p>
            )}
          </div>

          <div className="flex w-full flex-col gap-2 lg:w-auto">
            {interviewTask ? (
              <Button
                className="w-full shrink-0 lg:min-w-[12rem]"
                variant="onDark"
                size="lg"
                type="button"
                onClick={() => void startPlannedItem(interviewTask)}
              >
                进入语音模拟面试
                <ArrowRight size={16} />
              </Button>
            ) : phase === "unconfigured" ? (
              <Button className="w-full shrink-0 lg:min-w-[12rem]" variant="onDark" size="lg" asChild>
                <Link href="/setup">
                  准备并进入面试
                  <ArrowRight size={16} />
                </Link>
              </Button>
            ) : profile?.next_training && profileSourceSessionId ? (
              <Button
                className="w-full shrink-0 lg:min-w-[12rem]"
                variant="onDark"
                size="lg"
                type="button"
                disabled={startingRecommendation}
                onClick={() => void startWeaknessInterview()}
              >
                {startingRecommendation && <LoaderCircle className="spin" size={15} />}
                {startingRecommendation ? "正在准备来源证据" : "按弱项开语音面试"}
                <ArrowRight size={16} />
              </Button>
            ) : (
              <Button className="w-full shrink-0 lg:min-w-[12rem]" variant="onDark" size="lg" asChild>
                <Link href="/setup">
                  开始语音模拟面试
                  <ArrowRight size={16} />
                </Link>
              </Button>
            )}
          </div>
        </div>

        {phase === "unconfigured" && (
          <ol className="mt-5 grid gap-3 border-t border-white/15 pt-4 sm:grid-cols-3">
            {[
              { n: "1", t: "目标岗位", d: latestDraft?.target_role || "待填写" },
              { n: "2", t: "简历 / JD", d: latestDraft?.resume_filename || "待上传" },
              { n: "3", t: "校正理解", d: "确认后再进考场" },
            ].map((step) => (
              <li key={step.n} className="rounded-xl border border-white/15 bg-white/5 p-5">
                <span className="text-xs font-medium text-white">{step.n}. {step.t}</span>
                <span className="mt-1 block text-xs text-white/70">{step.d}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Active drill reminder */}
      {activeDrill && (
        <section className="mt-6 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-[var(--muted)]">未完成的短练</p>
              <strong className="mt-1 block text-[15px] text-[var(--ink)]">{activeDrill.title}</strong>
              <span className="mt-0.5 block text-xs text-[var(--muted)]">
                {COACHING_MODE_LABELS[activeDrill.mode]} · {activeDrill.status === "completed" ? "已完成" : activeDrill.status === "active" ? "进行中" : "待开始"}
              </span>
            </div>
            <Button variant="secondary" size="sm" asChild>
              <Link href={`/training/${activeDrill.id}`}>
                继续短练
                <ArrowRight size={14} />
              </Link>
            </Button>
          </div>
        </section>
      )}

      {/* Today's plan */}
      {otherTasks.length > 0 && (
        <section className="mt-6 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5" aria-label="今日辅助安排">
          <header className="mb-2 flex items-center gap-2">
            <CheckCircle2 className="text-[var(--accent)]" size={16} />
            <strong className="text-sm text-[var(--ink)]">今日安排</strong>
          </header>
          <div className="grid gap-2">
            {otherTasks.map((item) => (
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

      {/* Recent sessions */}
      {recent.length > 0 && (
        <section className="mt-8" aria-label="最近短练">
          <div className="mb-3 flex items-end justify-between gap-3">
            <h2 className="text-base font-medium text-[var(--text-primary)]">最近短练</h2>
          </div>
          <div className="grid gap-2">
            {recent.slice(0, 3).map((item) => (
              <Link
                key={item.id}
                href={`/training/${item.id}`}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 transition-[border-color,transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:border-[var(--border-hover)] hover:shadow-[var(--shadow-lift)]"
              >
                <span className="min-w-0">
                  <strong className="block truncate text-[14px]">{item.title}</strong>
                  <span className="mt-0.5 block truncate text-xs text-[var(--muted)]">
                    {COACHING_MODE_LABELS[item.mode]} · {item.turn_count} 轮 · {item.status === "completed" ? "已完成" : item.status === "active" ? "进行中" : "待开始"}
                  </span>
                </span>
                <ArrowRight size={15} className="text-[var(--muted)]" />
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Drill modes */}
      <section className="mt-10" aria-label="上场前辅助">
        <div className="mb-3">
          <h2 className="text-base font-medium text-[var(--text-primary)]">热身短练</h2>
        </div>
        <div className="grid grid-cols-3 gap-2.5 max-[900px]:grid-cols-1">
          {drillModes.map(({ href, title, description, icon: Icon }) => (
            <Link
              key={title}
              href={href}
              className={cn(
                "group grid grid-cols-[2.25rem_minmax(0,1fr)_auto] items-center gap-3 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5 text-[var(--text-primary)]",
                "transition-[border-color,transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:border-[var(--border-hover)] hover:shadow-[var(--shadow-lift)]",
              )}
            >
              <span className="grid size-9 place-items-center rounded-full bg-[var(--accent-light)] text-[var(--accent)]">
                <Icon size={16} />
              </span>
              <span className="min-w-0">
                <strong className="block text-sm">{title}</strong>
                <span className="mt-0.5 block text-xs text-[var(--muted)]">{description}</span>
              </span>
              <ArrowRight size={15} className="text-[var(--muted)] group-hover:text-[var(--accent)]" />
            </Link>
          ))}
        </div>
        {coaching?.next_mode && (
          <p className="mt-3 text-xs text-[var(--muted)]">
            画像建议的短练：{COACHING_MODE_LABELS[coaching.next_mode]}
            {coaching.next_focus ? ` · ${coaching.next_focus}` : ""}
            {" · "}
            <Link className="font-semibold text-[var(--accent)] hover:underline" href={`/training/new?mode=${coaching.next_mode}`}>
              可选
            </Link>
          </p>
        )}
      </section>
    </main>
  );
}

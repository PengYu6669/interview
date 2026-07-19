"use client";

import { ArrowLeft, ArrowRight, Clock3, LoaderCircle, Target } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import {
  COACHING_DIFFICULTY_LABELS,
  COACHING_DIMENSION_LABELS,
  COACHING_EXERCISE_LABELS,
  COACHING_MODE_LABELS,
  CoachingDifficulty,
  CoachingExerciseType,
  CoachingMode,
  CoachingSession,
  coachingSessionSchema,
} from "@/lib/coaching";
import { QUESTION_COACHING_SELECTION_KEY } from "@/lib/questions";

const exercises: Record<CoachingMode, CoachingExerciseType[]> = {
  structured_expression: ["star_story", "prep_pitch", "structure_puzzle"],
  business_sense: ["decision_simulation", "fermi_estimation"],
};

const fieldClass =
  "w-full rounded-lg border border-[var(--line)] bg-[var(--bg-canvas)] px-4 py-3 text-sm leading-relaxed text-[var(--ink)] outline-none focus:border-[var(--accent)] focus:shadow-[0_0_0_1px_var(--accent-light)]";

const choiceButtonClass =
  "min-h-[42px] rounded-md border border-[var(--line)] bg-[#fafbfb] px-3 text-xs text-[var(--muted)] transition-colors";

const choiceSelectedClass =
  "border-[var(--accent)] bg-[var(--accent-soft)] font-bold text-[var(--accent-dark)]";

export function CoachingSetup({
  mode,
  initialFocus = "",
  initialDifficulty = "guided",
  planItemId,
}: {
  mode: CoachingMode;
  initialFocus?: string;
  initialDifficulty?: CoachingDifficulty;
  planItemId?: string;
}) {
  const router = useRouter();
  const [role, setRole] = useState("AI 应用开发工程师");
  const [goal, setGoal] = useState(initialFocus);
  const [channel] = useState<"text" | "voice">("text");
  const [exercise, setExercise] = useState<CoachingExerciseType>(exercises[mode][0]);
  const [difficulty, setDifficulty] = useState<CoachingDifficulty>(initialDifficulty);
  const [session, setSession] = useState<CoachingSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sourceQuestions, setSourceQuestions] = useState<Array<{ id: string; title: string; framework: string }>>([]);

  useEffect(() => {
    if (mode !== "structured_expression") return;
    const timeout = window.setTimeout(() => {
      try {
        const raw = sessionStorage.getItem(QUESTION_COACHING_SELECTION_KEY);
        if (!raw) return;
        const parsed = JSON.parse(raw) as {
          questions?: Array<{ id?: string; title?: string; framework?: string }>;
        };
        const valid = (parsed.questions ?? [])
          .filter((item): item is { id: string; title: string; framework: string } =>
            Boolean(item.id && item.title && item.framework),
          )
          .slice(0, 1);
        setSourceQuestions(valid);
        if (valid[0]) {
          setGoal(`围绕「${valid[0].title}」练习结构化回答`);
          setExercise(valid[0].framework === "star" ? "star_story" : "prep_pitch");
        }
      } catch {
        sessionStorage.removeItem(QUESTION_COACHING_SELECTION_KEY);
      }
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [mode]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/coaching-sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          channel,
          target_role: role,
          training_goal: goal,
          source_ids: sourceQuestions.map((item) => item.id),
          exercise_type: exercise,
          difficulty,
          ...(planItemId ? { career_plan_item_id: planItemId } : {}),
        }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof payload === "object" && payload && "detail" in payload
            ? String(payload.detail)
            : "训练任务生成失败",
        );
      }
      const parsed = coachingSessionSchema.safeParse(payload);
      if (!parsed.success) throw new Error("训练服务返回了无效任务");
      setSession(parsed.data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "训练任务生成失败");
    } finally {
      setLoading(false);
    }
  }

  async function start() {
    if (!session) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/coaching-sessions/${session.id}/start`, { method: "POST" });
      if (!response.ok) {
        const payload: unknown = await response.json();
        throw new Error(
          typeof payload === "object" && payload && "detail" in payload
            ? String(payload.detail)
            : "训练暂时无法开始",
        );
      }
      router.push(`/training/${session.id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "训练暂时无法开始");
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto w-[min(1180px,calc(100%-48px))] pb-20 pt-14 max-[700px]:w-[calc(100%-28px)] max-[700px]:pt-8">
      <Link href="/training" className="back-link">
        <ArrowLeft size={15} />
        返回训练中心
      </Link>

      <header className="mt-4 flex items-end justify-between gap-7 pb-6 max-[620px]:flex-col max-[620px]:items-start">
        <div>
          <p className="eyebrow">{COACHING_MODE_LABELS[mode]}</p>
          <h1 className="mt-2.5 text-[30px] font-extrabold leading-tight text-[var(--ink)] max-[700px]:text-[27px]">
            设定本次训练目标
          </h1>
        </div>
      </header>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)_360px] items-start gap-6 max-[900px]:grid-cols-1">
        <form className="grid gap-5 rounded-xl border border-[var(--line)] bg-white p-6 text-[var(--ink)]" onSubmit={create}>
          <label className="grid gap-2">
            <span className="text-[13px] font-semibold">目标岗位</span>
            <input
              className={fieldClass}
              value={role}
              maxLength={150}
              onChange={(event) => setRole(event.target.value)}
              required
            />
          </label>

          <label className="grid gap-2">
            <span className="text-[13px] font-semibold">本次重点</span>
            <textarea
              className={cn(fieldClass, "min-h-28 resize-y")}
              value={goal}
              maxLength={500}
              onChange={(event) => setGoal(event.target.value)}
              placeholder={
                mode === "structured_expression"
                  ? "例如：项目介绍容易说得散，想练习结论先行"
                  : "例如：技术方案很熟，但不清楚如何连接业务指标"
              }
            />
          </label>

          {sourceQuestions.length > 0 && (
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-1 gap-x-3 border-l-[3px] border-[var(--accent)] bg-[var(--accent-soft)] px-3 py-2.5">
              <span className="text-xs text-[var(--muted)]">来自个人题库</span>
              <strong className="col-start-1 text-[13px]">{sourceQuestions[0].title}</strong>
              <button
                type="button"
                className="row-span-2 self-center border-0 bg-transparent text-xs text-[var(--accent-dark)]"
                onClick={() => {
                  setSourceQuestions([]);
                  sessionStorage.removeItem(QUESTION_COACHING_SELECTION_KEY);
                }}
              >
                移除
              </button>
            </div>
          )}

          <fieldset className="grid grid-cols-2 gap-1.5 border-0 max-[620px]:grid-cols-1">
            <legend className="col-span-full mb-0.5 text-[13px] font-semibold">训练题型</legend>
            {exercises[mode].map((item) => (
              <button
                key={item}
                type="button"
                className={cn(choiceButtonClass, exercise === item && choiceSelectedClass)}
                aria-pressed={exercise === item}
                onClick={() => setExercise(item)}
              >
                {COACHING_EXERCISE_LABELS[item]}
              </button>
            ))}
          </fieldset>

          <fieldset className="grid grid-cols-3 gap-1.5 border-0 max-[620px]:grid-cols-1">
            <legend className="col-span-full mb-0.5 text-[13px] font-semibold">提示强度</legend>
            {(["guided", "assisted", "pressure"] as CoachingDifficulty[]).map((item) => (
              <button
                key={item}
                type="button"
                className={cn(choiceButtonClass, difficulty === item && choiceSelectedClass)}
                aria-pressed={difficulty === item}
                onClick={() => setDifficulty(item)}
              >
                {COACHING_DIFFICULTY_LABELS[item]}
              </button>
            ))}
          </fieldset>

          {error && (
            <p className="border-l-[3px] border-[var(--danger)] bg-[#fff4f2] px-3 py-2.5 text-[13px] leading-relaxed text-[#973f37]">
              {error}
            </p>
          )}

          <Button className="w-full" type="submit" disabled={loading || !role.trim()}>
            {loading ? (
              <>
                <LoaderCircle className="spin" size={16} />
                正在生成训练任务
              </>
            ) : (
              <>
                生成训练任务
                <ArrowRight size={16} />
              </>
            )}
          </Button>
        </form>

        <aside
          className="sticky top-[88px] rounded-xl border border-[var(--line)] bg-white p-[22px] text-[var(--ink)] max-[900px]:static max-[620px]:p-[18px]"
          aria-live="polite"
        >
          {!session ? (
            <>
              <span className="grid size-[38px] place-items-center rounded-md bg-[var(--soft)] text-[var(--accent-dark)]">
                <Target size={20} />
              </span>
              <h2 className="mt-3.5 text-lg font-semibold">训练任务</h2>
            </>
          ) : (
            <>
              <p className="eyebrow">任务已生成</p>
              <h2 className="mt-3.5 text-lg font-semibold">{session.task.title}</h2>
              <p className="mt-2 text-[13px] leading-relaxed text-[var(--muted)]">{session.task.objective}</p>

              {session.task.source_questions?.[0] && (
                <blockquote className="mt-3.5 border-l-[3px] border-[var(--accent)] bg-[var(--bg-subtle)] px-3 py-2.5">
                  <strong className="block text-[13px]">{session.task.source_questions[0].title}</strong>
                  <span className="mt-1.5 block text-xs leading-relaxed text-[var(--text-secondary)]">
                    {session.task.source_questions[0].prompt}
                  </span>
                  {session.task.source_questions[0].evidence_quotes?.[0] && (
                    <small className="mt-1.5 block text-xs leading-snug text-[var(--muted)]">
                      原文：{session.task.source_questions[0].evidence_quotes[0]}
                    </small>
                  )}
                </blockquote>
              )}

              <dl className="my-5 border-y border-[var(--line)] py-2">
                <div className="flex justify-between gap-3.5 py-2 text-xs">
                  <dt className="text-[var(--muted)]">题型</dt>
                  <dd className="text-right font-semibold">{COACHING_EXERCISE_LABELS[session.task.exercise_type]}</dd>
                </div>
                <div className="flex justify-between gap-3.5 py-2 text-xs">
                  <dt className="text-[var(--muted)]">难度</dt>
                  <dd className="text-right font-semibold">{COACHING_DIFFICULTY_LABELS[session.task.difficulty]}</dd>
                </div>
                <div className="flex justify-between gap-3.5 py-2 text-xs">
                  <dt className="text-[var(--muted)]">预计时长</dt>
                  <dd className="inline-flex items-center justify-end gap-1 text-right font-semibold">
                    <Clock3 size={13} />
                    {session.task.estimated_minutes} 分钟
                  </dd>
                </div>
                <div className="flex justify-between gap-3.5 py-2 text-xs">
                  <dt className="text-[var(--muted)]">训练形式</dt>
                  <dd className="text-right font-semibold">
                    {session.channel === "voice" ? "语音对话" : "文字对话"}
                  </dd>
                </div>
              </dl>

              <p className="text-[13px] leading-relaxed text-[var(--muted)]">{session.task.scenario}</p>

              <div className="mt-3.5 flex flex-wrap gap-1.5">
                {session.task.dimensions.map((item) => (
                  <span
                    key={item}
                    className="rounded border border-[var(--border-hover)] bg-[var(--accent-soft)] px-2 py-1 text-xs text-[var(--text-secondary)]"
                  >
                    {COACHING_DIMENSION_LABELS[item] ?? item}
                  </span>
                ))}
              </div>

              <Button className="mt-4 w-full" type="button" disabled={loading} onClick={start}>
                确认并开始
                <ArrowRight size={16} />
              </Button>
            </>
          )}
        </aside>
      </div>
    </main>
  );
}

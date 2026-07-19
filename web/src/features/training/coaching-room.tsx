"use client";

import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  Mic,
  RotateCcw,
  Sparkles,
  Square,
  Target,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/error-banner";
import { cn } from "@/lib/cn";
import {
  COACHING_DIFFICULTY_LABELS,
  COACHING_DIMENSION_LABELS,
  COACHING_EXERCISE_LABELS,
  COACHING_MODE_LABELS,
} from "@/lib/coaching";

import { useCoachingSession } from "./use-coaching-session";

function formatTime(seconds: number) {
  const safe = Math.max(0, seconds);
  return `${Math.floor(safe / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
}

const pageClass =
  "mx-auto w-[min(1180px,calc(100%-48px))] pb-20 pt-14 max-[700px]:w-[calc(100%-28px)] max-[700px]:pt-8";

const panelClass = "rounded-xl border border-[var(--line)] bg-white text-[var(--ink)]";

const errorClass =
  "border-l-[3px] border-[var(--danger)] bg-[#fff4f2] px-3 py-2.5 text-[13px] leading-relaxed text-[#973f37]";

const dimensionChipClass =
  "rounded border border-[var(--border-hover)] bg-[var(--accent-soft)] px-2 py-1 text-xs text-[var(--text-secondary)]";

export function CoachingRoom({ sessionId }: { sessionId: string }) {
  const {
    session,
    answer,
    setAnswer,
    setAnswerMode,
    loading,
    submitting,
    error,
    remaining,
    puzzleAssignments,
    setPuzzleAssignments,
    puzzleComplete,
    puzzleError,
    voice,
    reload,
    start,
    submit,
    checkPuzzle,
  } = useCoachingSession(sessionId);

  if (loading) {
    return (
      <main className={pageClass}>
        <div className="flex min-h-[116px] items-center gap-3 border-y border-[var(--line)] text-[13px] text-[var(--muted)]">
          <LoaderCircle className="spin" size={18} />
          正在恢复训练
        </div>
      </main>
    );
  }

  if (!session) {
    return (
      <main className={pageClass}>
        <ErrorBanner message={error || "找不到这项训练"} onRetry={() => void reload()} />
      </main>
    );
  }

  const latest = session.turns.at(-1);
  const comparison = latest?.decision.comparison;
  const nextPractice = latest?.decision.next_practice;
  const showScaffold = session.task.difficulty !== "pressure" || session.turns.length > 0;
  const facts = session.task.facts ?? [];
  const scaffold = session.task.scaffold ?? [];

  return (
    <main className={pageClass}>
      {/* Header */}
      <header className="flex items-end justify-between gap-7 pb-6 max-[620px]:flex-col max-[620px]:items-start">
        <div>
          <p className="eyebrow">{COACHING_MODE_LABELS[session.mode]}</p>
          <h1 className="mt-2 text-[30px] font-extrabold leading-tight text-[var(--ink)] max-[620px]:text-[27px]">
            {session.task.title}
          </h1>
          <p className="mt-2.5 max-w-[720px] text-sm leading-[1.75] text-[var(--muted)]">
            {session.task.objective}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <span className="rounded border border-[var(--line)] bg-white px-2 py-1.5 text-xs text-[var(--muted)]">
            {COACHING_EXERCISE_LABELS[session.task.exercise_type]}
          </span>
          <span className="rounded border border-[var(--line)] bg-white px-2 py-1.5 text-xs text-[var(--muted)]">
            {COACHING_DIFFICULTY_LABELS[session.task.difficulty]}
          </span>
        </div>
      </header>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)_310px] items-start gap-5 max-[900px]:grid-cols-1">
        {/* Main panel */}
        <section className={cn(panelClass, "overflow-hidden")}>
          <div className="border-b border-[var(--line)] px-[22px] py-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold">
                {session.status === "completed"
                  ? "训练完成"
                  : session.turns.length
                    ? "第 2 次作答"
                    : "第 1 次作答"}
              </h2>
              {session.status === "active" && puzzleComplete && (
                <span
                  className={cn(
                    "inline-flex items-center gap-1 font-mono text-xs text-[var(--accent-dark)]",
                    remaining === 0 && "text-[var(--danger)]",
                  )}
                >
                  <Clock3 size={14} />
                  {remaining ? formatTime(remaining) : "时间到，完成当前思路后提交"}
                </span>
              )}
            </div>
            <p className="mt-1.5 text-[13px] text-[var(--muted)]">{session.task.scenario}</p>
            {facts.length > 0 && (
              <dl className="mt-3 grid grid-cols-2 gap-1.5 max-[620px]:grid-cols-1">
                {facts.map((fact) => (
                  <div key={fact.label} className="border-l-2 border-[var(--border-hover)] bg-[var(--bg-subtle)] px-2.5 py-1.5">
                    <dt className="text-xs text-[var(--muted)]">{fact.label}</dt>
                    <dd className="mt-0.5 text-xs font-semibold">{fact.value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>

          {session.status === "planned" ? (
            <div className="border-t border-[var(--line)] px-[22px] py-5">
              {error && <ErrorBanner message={error} />}
              <Button className="mt-3 w-full" disabled={submitting} onClick={start}>
                开始训练
                <ArrowRight size={16} />
              </Button>
            </div>
          ) : (
            <>
              {/* Puzzle */}
              {!puzzleComplete && session.task.puzzle && (
                <section className="grid gap-3 p-6">
                  <span className="eyebrow">结构热身</span>
                  <h2 className="text-lg font-semibold">先拼出回答骨架</h2>
                  <p className="text-[13px] text-[var(--muted)]">{session.task.puzzle.instruction}</p>
                  <div className="grid gap-1.5">
                    {session.task.puzzle.fragments.map((fragment) => (
                      <label
                        key={fragment.id}
                        className="grid grid-cols-[minmax(0,1fr)_150px] items-center gap-3 rounded-md border border-[var(--line)] px-2.5 py-2 max-[620px]:grid-cols-1"
                      >
                        <span className="text-[13px] leading-relaxed">{fragment.text}</span>
                        <select
                          className="min-h-9 rounded border border-[var(--line)] bg-white px-2 text-xs text-[var(--ink)]"
                          value={puzzleAssignments[fragment.id] ?? ""}
                          onChange={(event) =>
                            setPuzzleAssignments((current) => ({
                              ...current,
                              [fragment.id]: event.target.value,
                            }))
                          }
                        >
                          <option value="">选择位置</option>
                          {scaffold.map((step) => (
                            <option value={step.key} key={step.key}>{step.label}</option>
                          ))}
                        </select>
                      </label>
                    ))}
                  </div>
                  {puzzleError && <p className={errorClass}>{puzzleError}</p>}
                  <Button type="button" onClick={checkPuzzle}>
                    检查结构
                    <ArrowRight size={15} />
                  </Button>
                </section>
              )}

              {puzzleComplete && (
                <div className="grid gap-[18px] p-6">
                  {/* Scaffold */}
                  {showScaffold && (
                    <section className="grid grid-cols-4 gap-1.5 max-[620px]:grid-cols-2" aria-label="回答结构">
                      {scaffold.map((step, index) => (
                        <article
                          key={step.key}
                          className="flex min-h-[72px] gap-2 rounded-md border border-[var(--border-hover)] bg-[var(--bg-subtle)] p-2.5"
                        >
                          <span className="grid size-[22px] shrink-0 place-items-center rounded-full bg-[var(--accent)] text-xs font-bold text-white">
                            {index + 1}
                          </span>
                          <div>
                            <strong className="text-xs">{step.label}</strong>
                            {session.task.difficulty === "guided" && (
                              <p className="mt-1 text-xs leading-snug text-[var(--muted)]">{step.prompt}</p>
                            )}
                          </div>
                        </article>
                      ))}
                    </section>
                  )}

                  {/* Turns */}
                  {session.turns.map((turn) => {
                    const segments = turn.decision.evidence_segments ?? [];
                    const gaps = turn.decision.priority_gaps ?? [];
                    const delivery = turn.decision.delivery_metrics;
                    return (
                      <article key={turn.id} className="grid gap-2.5 border-t border-[var(--line)] pt-[18px]">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-extrabold text-[var(--accent-dark)]">
                            第 {turn.attempt_number ?? turn.sequence} 次回答
                          </span>
                          {turn.elapsed_seconds != null && (
                            <small className="font-mono text-xs text-[var(--muted)]">
                              {formatTime(turn.elapsed_seconds)}
                            </small>
                          )}
                        </div>
                        <p className="whitespace-pre-wrap text-sm leading-[1.75]">{turn.answer}</p>
                        {delivery && (
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="rounded bg-[var(--bg-subtle)] px-1.5 py-1 text-xs text-[var(--text-secondary)]">{delivery.character_count} 字</span>
                            {delivery.characters_per_minute !== null && (
                              <span className="rounded bg-[var(--bg-subtle)] px-1.5 py-1 text-xs text-[var(--text-secondary)]">{delivery.characters_per_minute} 字/分钟</span>
                            )}
                            <span className="rounded bg-[var(--bg-subtle)] px-1.5 py-1 text-xs text-[var(--text-secondary)]">填充词 {delivery.filler_total} 次</span>
                            {delivery.source === "voice_transcript" && (
                              <small className="w-full text-xs text-[var(--muted)]">基于转写估算，语音服务可能清理部分语气词</small>
                            )}
                          </div>
                        )}
                        {segments.length > 0 && (
                          <div className="grid gap-1.5">
                            {segments.map((item) => (
                              <blockquote key={`${item.key}-${item.evidence_quote}`} className="border-l-[3px] border-[var(--border-hover)] bg-[var(--bg-subtle)] px-2.5 py-2 text-xs leading-relaxed text-[var(--text-secondary)]">
                                <span className="mr-1.5 font-extrabold text-[var(--accent-dark)]">{item.label}</span>
                                {item.evidence_quote}
                              </blockquote>
                            ))}
                          </div>
                        )}
                        {gaps.length > 0 && (
                          <div className="grid gap-1.5">
                            {gaps.map((gap) => (
                              <article key={gap.dimension} className="flex gap-2 border border-[#ebcda6] bg-[#fff9ef] p-2.5">
                                <Target className="mt-0.5 shrink-0 text-[#9a671d]" size={16} />
                                <div>
                                  <strong className="text-xs">{COACHING_DIMENSION_LABELS[gap.dimension] ?? gap.dimension}</strong>
                                  <p className="mt-0.5 text-xs leading-snug text-[#705838]">{gap.diagnosis}</p>
                                  <small className="mt-0.5 block text-xs leading-snug text-[#705838]">{gap.retry_prompt}</small>
                                </div>
                              </article>
                            ))}
                          </div>
                        )}
                      </article>
                    );
                  })}

                  {/* Current question */}
                  {session.current_question && (
                    <div className="border-l-[3px] border-[var(--accent)] bg-[var(--bg-subtle)] px-[18px] py-4">
                      <span className="text-xs font-bold text-[var(--accent-dark)]">
                        {latest ? "原题重答" : "训练题目"}
                      </span>
                      <p className="mt-2 text-base leading-[1.75]">{session.current_question}</p>
                    </div>
                  )}

                  {/* Comparison */}
                  {comparison && (
                    <section className="grid gap-3 border-t border-[var(--line)] pt-5">
                      <div className="flex items-center gap-1.5">
                        <Sparkles className="text-[var(--accent)]" size={18} />
                        <h2 className="text-base font-semibold">两次回答对比</h2>
                      </div>
                      <p className="text-[13px] leading-relaxed text-[var(--muted)]">{comparison.overall_summary}</p>
                      <div className="grid gap-2">
                        {comparison.items.map((item) => (
                          <article
                            key={item.dimension}
                            className={cn(
                              "border border-[var(--line)] border-l-[3px] border-l-[var(--border-hover)] p-2.5",
                              item.change === "improved" && "border-l-[var(--success)]",
                              item.change === "regressed" && "border-l-[var(--danger)]",
                            )}
                          >
                            <header className="flex justify-between gap-2.5">
                              <strong className="text-xs">{COACHING_DIMENSION_LABELS[item.dimension] ?? item.dimension}</strong>
                              <span className="text-xs text-[var(--muted)]">
                                {item.change === "improved" ? "有进步" : item.change === "regressed" ? "需回看" : item.change === "stable" ? "基本稳定" : "证据不足"}
                              </span>
                            </header>
                            <div className="mt-2 grid grid-cols-[1fr_auto_1fr] items-center gap-2 max-[620px]:grid-cols-1">
                              <blockquote className="min-w-0 bg-[var(--bg-subtle)] p-2 text-xs leading-snug">
                                <small className="mb-0.5 block text-[var(--muted)]">第一次</small>
                                {item.before_quote ?? "未找到有效证据"}
                              </blockquote>
                              <ArrowRight className="max-[620px]:rotate-90" size={15} />
                              <blockquote className="min-w-0 bg-[var(--bg-subtle)] p-2 text-xs leading-snug">
                                <small className="mb-0.5 block text-[var(--muted)]">第二次</small>
                                {item.after_quote ?? "未找到有效证据"}
                              </blockquote>
                            </div>
                            <p className="mt-1.5 text-xs text-[var(--muted)]">{item.explanation}</p>
                          </article>
                        ))}
                      </div>
                    </section>
                  )}
                </div>
              )}

              {/* Answer form */}
              {puzzleComplete && session.status === "active" && (
                <form className="border-t border-[var(--line)] px-[22px] py-5" onSubmit={submit}>
                  <textarea
                    className="min-h-[150px] w-full resize-y rounded-lg border border-[var(--line)] bg-[var(--bg-canvas)] p-4 text-sm leading-[1.7] text-[var(--ink)] outline-none focus:border-[var(--accent)] focus:shadow-[0_0_0_1px_var(--accent-light)]"
                    value={answer}
                    maxLength={20_000}
                    onChange={(event) => {
                      setAnswer(event.target.value);
                      setAnswerMode("text");
                    }}
                    placeholder={
                      session.turns.length
                        ? "根据两个重点缺口重答同一道题，优先变得更具体，不必单纯变长。"
                        : "按真实面试节奏完整回答，不需要追求一次说完美。"
                    }
                  />
                  {(error || voice.error) && (
                    <ErrorBanner message={error || voice.error} />
                  )}
                  <div className="mt-3 flex items-center justify-between gap-3 max-[620px]:flex-col max-[620px]:items-stretch">
                    <span className="text-xs text-[var(--muted)]">
                      {voice.status === "listening"
                        ? `正在录音 ${voice.seconds} 秒`
                        : voice.status === "recognizing"
                          ? "正在整理转写"
                          : `${answer.length} / 20000`}
                    </span>
                    <div className="flex items-center gap-2 max-[620px]:grid max-[620px]:w-full max-[620px]:grid-cols-2">
                      {session.channel === "voice" &&
                        (voice.status === "listening" ? (
                          <Button variant="secondary" type="button" onClick={() => void voice.stop()}>
                            <Square size={14} />
                            停止
                          </Button>
                        ) : (
                          <Button
                            variant="secondary"
                            disabled={voice.status !== "idle" || submitting}
                            type="button"
                            onClick={() => void voice.start()}
                          >
                            <Mic size={15} />
                            语音回答
                          </Button>
                        ))}
                      <Button
                        disabled={submitting || voice.status !== "idle" || !answer.trim()}
                        type="submit"
                      >
                        {submitting ? (
                          <>
                            <LoaderCircle className="spin" size={16} />
                            正在分析
                          </>
                        ) : (
                          <>
                            {session.turns.length ? "提交重答" : "提交首次回答"}
                            <ArrowRight size={16} />
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                </form>
              )}
            </>
          )}
        </section>

        {/* Sidebar */}
        <aside className={cn(panelClass, "sticky top-[88px] p-5 max-[900px]:static")}>
          <h3 className="text-sm font-semibold">本次训练目标</h3>
          <div className="mt-3.5 flex flex-wrap gap-1.5">
            {session.task.dimensions.map((item) => (
              <span key={item} className={dimensionChipClass}>
                {COACHING_DIMENSION_LABELS[item] ?? item}
              </span>
            ))}
          </div>
          {session.status === "completed" && nextPractice && (
            <div className="mt-[18px] grid gap-2 border-t border-[var(--line)] pt-4">
              <CheckCircle2 className="text-[var(--success)]" size={18} />
              <strong className="text-[13px]">下一次 10 分钟</strong>
              <p className="text-xs leading-relaxed text-[var(--muted)]">{nextPractice.focus}</p>
              <Button className="w-full" asChild>
                <Link
                  href={`/training/new?mode=${session.mode}&difficulty=${nextPractice.recommended_difficulty}&focus=${encodeURIComponent(nextPractice.focus)}`}
                >
                  <RotateCcw size={15} />
                  按建议再练
                </Link>
              </Button>
            </div>
          )}
          {session.status === "completed" && !nextPractice && (
            <Button className="mt-4 w-full" variant="secondary" asChild>
              <Link href={`/training/new?mode=${session.mode}`}>
                <RotateCcw size={15} />
                再练一次
              </Link>
            </Button>
          )}
        </aside>
      </div>
    </main>
  );
}

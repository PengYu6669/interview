"use client";

import { ArrowRight, CheckCircle2, Clock3, LoaderCircle, Mic, RotateCcw, Sparkles, Square, Target } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { COACHING_DIFFICULTY_LABELS, COACHING_DIMENSION_LABELS, COACHING_EXERCISE_LABELS, COACHING_MODE_LABELS, CoachingSession, coachingSessionSchema } from "@/lib/coaching";

import styles from "./training.module.css";
import { useVoiceTranscription } from "./use-voice-transcription";

function formatTime(seconds: number) {
  const safe = Math.max(0, seconds);
  return `${Math.floor(safe / 60).toString().padStart(2, "0")}:${(safe % 60).toString().padStart(2, "0")}`;
}

export function CoachingRoom({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<CoachingSession | null>(null);
  const [answer, setAnswer] = useState("");
  const [answerMode, setAnswerMode] = useState<"text" | "voice">("text");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [remaining, setRemaining] = useState(0);
  const [puzzleAssignments, setPuzzleAssignments] = useState<Record<string, string>>({});
  const [puzzleComplete, setPuzzleComplete] = useState(false);
  const [puzzleError, setPuzzleError] = useState("");
  const attemptStartedAt = useRef(0);
  const voice = useVoiceTranscription(sessionId, (text) => { setAnswer(text); setAnswerMode("voice"); });

  const applySession = useCallback((data: CoachingSession) => {
    setSession(data);
    setRemaining(data.task.time_limit_seconds);
    setPuzzleComplete(data.turns.length > 0 || !data.task.puzzle);
    attemptStartedAt.current = Date.now();
  }, []);

  const fetchSession = useCallback(async () => {
    const response = await fetch(`/api/coaching-sessions/${sessionId}`, { cache: "no-store" });
    const payload: unknown = await response.json();
    if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "训练读取失败");
    const parsed = coachingSessionSchema.safeParse(payload);
    if (!parsed.success) throw new Error("训练服务返回了无效数据");
    return parsed.data;
  }, [sessionId]);

  useEffect(() => {
    let mounted = true;
    void fetchSession().then((data) => { if (mounted) applySession(data); }).catch((cause: unknown) => { if (mounted) setError(cause instanceof Error ? cause.message : "训练读取失败"); }).finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [applySession, fetchSession]);

  useEffect(() => {
    if (!session || session.status !== "active" || !puzzleComplete) return;
    const timer = window.setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1_000);
    return () => window.clearInterval(timer);
  }, [puzzleComplete, session]);

  async function reload() {
    setLoading(true); setError("");
    try { applySession(await fetchSession()); } catch (cause) { setError(cause instanceof Error ? cause.message : "训练读取失败"); } finally { setLoading(false); }
  }

  async function start() {
    setSubmitting(true); setError("");
    try {
      const response = await fetch(`/api/coaching-sessions/${sessionId}/start`, { method: "POST" });
      const payload: unknown = await response.json();
      const parsed = coachingSessionSchema.safeParse(payload);
      if (!response.ok || !parsed.success) throw new Error("训练暂时无法开始");
      applySession(parsed.data);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "训练暂时无法开始"); } finally { setSubmitting(false); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); if (!answer.trim()) return; setSubmitting(true); setError("");
    try {
      const elapsedSeconds = Math.min(3_600, Math.max(0, Math.round((Date.now() - attemptStartedAt.current) / 1_000)));
      const response = await fetch(`/api/coaching-sessions/${sessionId}/answers`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ client_message_id: crypto.randomUUID(), answer: answer.trim(), answer_mode: answerMode, elapsed_seconds: elapsedSeconds }) });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "回答提交失败");
      const parsed = coachingSessionSchema.safeParse(payload);
      if (!parsed.success) throw new Error("训练服务返回了无效评价");
      applySession(parsed.data); setAnswer(""); setAnswerMode("text");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "回答提交失败"); } finally { setSubmitting(false); }
  }

  function checkPuzzle() {
    const fragments = session?.task.puzzle?.fragments ?? [];
    const incorrect = fragments.some((item) => puzzleAssignments[item.id] !== item.target_key);
    if (incorrect) { setPuzzleError("还有片段位置不准确，按表达顺序再检查一次。"); return; }
    setPuzzleError(""); setPuzzleComplete(true); setRemaining(session?.task.time_limit_seconds ?? 0); attemptStartedAt.current = Date.now();
  }

  if (loading) return <main className={styles.page}><div className={styles.empty}><LoaderCircle className="spin" size={18} />正在恢复训练</div></main>;
  if (!session) return <main className={styles.page}><p className={styles.error}>{error || "找不到这项训练"}</p><button className={styles.secondary} onClick={() => void reload()}>重新读取</button></main>;
  const latest = session.turns.at(-1);
  const comparison = latest?.decision.comparison;
  const nextPractice = latest?.decision.next_practice;
  const showScaffold = session.task.difficulty !== "pressure" || session.turns.length > 0;
  const facts = session.task.facts ?? [];
  const scaffold = session.task.scaffold ?? [];

  return <main className={styles.page}>
    <header className={styles.intro}><div><p className="eyebrow">{COACHING_MODE_LABELS[session.mode]}</p><h1>{session.task.title}</h1><p>{session.task.objective}</p></div><div className={styles.taskMeta}><span>{COACHING_EXERCISE_LABELS[session.task.exercise_type]}</span><span>{COACHING_DIFFICULTY_LABELS[session.task.difficulty]}</span></div></header>
    <div className={styles.room}>
      <section className={styles.roomMain}>
        <div className={styles.roomHeader}><div><h2>{session.status === "completed" ? "训练完成" : session.turns.length ? "第 2 次作答" : "第 1 次作答"}</h2>{session.status === "active" && puzzleComplete && <span className={`${styles.timer} ${remaining === 0 ? styles.timeUp : ""}`}><Clock3 size={14} />{remaining ? formatTime(remaining) : "时间到，完成当前思路后提交"}</span>}</div><p>{session.task.scenario}</p>{facts.length > 0 && <dl className={styles.factStrip}>{facts.map((fact) => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl>}</div>
        {session.status === "planned" ? <div className={styles.composer}>{error && <p className={styles.error}>{error}</p>}<button className={`${styles.primary} ${styles.full}`} disabled={submitting} onClick={start}>开始训练 <ArrowRight size={16} /></button></div> : <>
          {!puzzleComplete && session.task.puzzle && <section className={styles.puzzle}><span className="eyebrow">结构热身</span><h2>先拼出回答骨架</h2><p>{session.task.puzzle.instruction}</p><div className={styles.puzzleList}>{session.task.puzzle.fragments.map((fragment) => <label key={fragment.id}><span>{fragment.text}</span><select value={puzzleAssignments[fragment.id] ?? ""} onChange={(event) => setPuzzleAssignments((current) => ({ ...current, [fragment.id]: event.target.value }))}><option value="">选择位置</option>{scaffold.map((step) => <option value={step.key} key={step.key}>{step.label}</option>)}</select></label>)}</div>{puzzleError && <p className={styles.error}>{puzzleError}</p>}<button className={styles.primary} type="button" onClick={checkPuzzle}>检查结构 <ArrowRight size={15} /></button></section>}
          {puzzleComplete && <div className={styles.conversation}>
            {showScaffold && <section className={styles.scaffold} aria-label="回答结构">{scaffold.map((step, index) => <article key={step.key}><span>{index + 1}</span><div><strong>{step.label}</strong>{session.task.difficulty === "guided" && <p>{step.prompt}</p>}</div></article>)}</section>}
            {session.turns.map((turn) => { const segments = turn.decision.evidence_segments ?? []; const gaps = turn.decision.priority_gaps ?? []; const delivery = turn.decision.delivery_metrics; return <article className={styles.turn} key={turn.id}><div className={styles.attemptHeading}><span>第 {turn.attempt_number ?? turn.sequence} 次回答</span>{turn.elapsed_seconds != null && <small>{formatTime(turn.elapsed_seconds)}</small>}</div><p className={styles.answer}>{turn.answer}</p>{delivery && <div className={styles.deliveryMetrics}><span>{delivery.character_count} 字</span>{delivery.characters_per_minute !== null && <span>{delivery.characters_per_minute} 字/分钟</span>}<span>填充词 {delivery.filler_total} 次</span>{delivery.source === "voice_transcript" && <small>基于转写估算，语音服务可能清理部分语气词</small>}</div>}{segments.length > 0 && <div className={styles.evidenceMap}>{segments.map((item) => <blockquote key={`${item.key}-${item.evidence_quote}`}><span>{item.label}</span>{item.evidence_quote}</blockquote>)}</div>}{gaps.length > 0 && <div className={styles.gapList}>{gaps.map((gap) => <article key={gap.dimension}><Target size={16} /><div><strong>{COACHING_DIMENSION_LABELS[gap.dimension] ?? gap.dimension}</strong><p>{gap.diagnosis}</p><small>{gap.retry_prompt}</small></div></article>)}</div>}</article>; })}
            {session.current_question && <div className={styles.questionBlock}><span>{latest ? "原题重答" : "训练题目"}</span><p>{session.current_question}</p></div>}
            {comparison && <section className={styles.comparison}><div><Sparkles size={18} /><h2>两次回答对比</h2></div><p>{comparison.overall_summary}</p><div>{comparison.items.map((item) => <article className={styles[item.change]} key={item.dimension}><header><strong>{COACHING_DIMENSION_LABELS[item.dimension] ?? item.dimension}</strong><span>{item.change === "improved" ? "有进步" : item.change === "regressed" ? "需回看" : item.change === "stable" ? "基本稳定" : "证据不足"}</span></header><div><blockquote><small>第一次</small>{item.before_quote ?? "未找到有效证据"}</blockquote><ArrowRight size={15} /><blockquote><small>第二次</small>{item.after_quote ?? "未找到有效证据"}</blockquote></div><p>{item.explanation}</p></article>)}</div></section>}
          </div>}
          {puzzleComplete && session.status === "active" && <form className={styles.composer} onSubmit={submit}><textarea value={answer} maxLength={20_000} onChange={(event) => { setAnswer(event.target.value); setAnswerMode("text"); }} placeholder={session.turns.length ? "根据两个重点缺口重答同一道题，优先变得更具体，不必单纯变长。" : "按真实面试节奏完整回答，不需要追求一次说完美。"} />{(error || voice.error) && <p className={styles.error}>{error || voice.error}</p>}<div className={styles.composerActions}><span>{voice.status === "listening" ? `正在录音 ${voice.seconds} 秒` : voice.status === "recognizing" ? "正在整理转写" : `${answer.length} / 20000`}</span><div className={styles.composerButtons}>{session.channel === "voice" && (voice.status === "listening" ? <button className={styles.secondary} type="button" onClick={() => void voice.stop()}><Square size={14} />停止</button> : <button className={styles.secondary} disabled={voice.status !== "idle" || submitting} type="button" onClick={() => void voice.start()}><Mic size={15} />语音回答</button>)}<button className={styles.primary} disabled={submitting || voice.status !== "idle" || !answer.trim()} type="submit">{submitting ? <><LoaderCircle className="spin" size={16} />正在分析</> : <>{session.turns.length ? "提交重答" : "提交首次回答"}<ArrowRight size={16} /></>}</button></div></div></form>}
        </>}
      </section>
      <aside className={styles.roomSide}><h3>本次训练目标</h3><div className={styles.dimensionList}>{session.task.dimensions.map((item) => <span key={item}>{COACHING_DIMENSION_LABELS[item] ?? item}</span>)}</div><p>只根据你的原句证据评价。第一次找关键缺口，第二次验证是否真的改善。</p>{session.status === "completed" && nextPractice && <div className={styles.nextPractice}><CheckCircle2 size={18} /><strong>下一次 10 分钟</strong><p>{nextPractice.focus}</p><Link href={`/training/new?mode=${session.mode}&difficulty=${nextPractice.recommended_difficulty}&focus=${encodeURIComponent(nextPractice.focus)}`} className={`${styles.primary} ${styles.full}`}><RotateCcw size={15} />按建议再练</Link></div>}{session.status === "completed" && !nextPractice && <Link href={`/training/new?mode=${session.mode}`} className={`${styles.secondary} ${styles.full}`}><RotateCcw size={15} />再练一次</Link>}</aside>
    </div>
  </main>;
}

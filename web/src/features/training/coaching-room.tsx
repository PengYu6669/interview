"use client";

import { ArrowRight, CheckCircle2, LoaderCircle, Mic, RotateCcw, Square } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { COACHING_DIMENSION_LABELS, COACHING_MODE_LABELS, CoachingSession, coachingSessionSchema } from "@/lib/coaching";

import styles from "./training.module.css";
import { useVoiceTranscription } from "./use-voice-transcription";

export function CoachingRoom({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<CoachingSession | null>(null);
  const [answer, setAnswer] = useState("");
  const [answerMode, setAnswerMode] = useState<"text" | "voice">("text");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const voice = useVoiceTranscription(sessionId, (text) => { setAnswer(text); setAnswerMode("voice"); });

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
    void fetchSession().then((data) => { if (mounted) setSession(data); }).catch((cause: unknown) => { if (mounted) setError(cause instanceof Error ? cause.message : "训练读取失败"); }).finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [fetchSession]);

  async function reload() {
    setLoading(true); setError("");
    try { setSession(await fetchSession()); } catch (cause) { setError(cause instanceof Error ? cause.message : "训练读取失败"); } finally { setLoading(false); }
  }

  async function start() {
    setSubmitting(true); setError("");
    try {
      const response = await fetch(`/api/coaching-sessions/${sessionId}/start`, { method: "POST" });
      const parsed = coachingSessionSchema.safeParse(await response.json());
      if (!response.ok || !parsed.success) throw new Error("训练暂时无法开始");
      setSession(parsed.data);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "训练暂时无法开始"); } finally { setSubmitting(false); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); if (!answer.trim()) return; setSubmitting(true); setError("");
    try {
      const response = await fetch(`/api/coaching-sessions/${sessionId}/answers`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ client_message_id: crypto.randomUUID(), answer: answer.trim(), answer_mode: answerMode }) });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "回答提交失败");
      const parsed = coachingSessionSchema.safeParse(payload);
      if (!parsed.success) throw new Error("训练服务返回了无效评价");
      setSession(parsed.data); setAnswer(""); setAnswerMode("text");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "回答提交失败"); } finally { setSubmitting(false); }
  }

  if (loading) return <main className={styles.page}><div className={styles.empty}><LoaderCircle className="spin" size={18} />正在恢复训练</div></main>;
  if (!session) return <main className={styles.page}><p className={styles.error}>{error || "找不到这项训练"}</p><button className={styles.secondary} onClick={() => void reload()}>重新读取</button></main>;
  const latest = session.turns.at(-1);

  return <main className={styles.page}>
    <header className={styles.intro}><div><p className="eyebrow">{COACHING_MODE_LABELS[session.mode]}</p><h1>{session.task.title}</h1><p>{session.task.objective}</p></div>{session.status === "completed" && <Link className={styles.secondary} href="/training">返回训练中心</Link>}</header>
    <div className={styles.room}>
      <section className={styles.roomMain}>
        <div className={styles.roomHeader}><h2>{session.status === "completed" ? "训练完成" : `第 ${session.turns.length + 1} 轮`}</h2><p>{session.task.scenario}</p></div>
        <div className={styles.conversation}>
          {session.turns.map((turn) => <article className={styles.turn} key={turn.id}><span className={styles.turnLabel}>你的回答</span><p className={styles.answer}>{turn.answer}</p><span className={styles.turnLabel}>训练教练</span><p className={styles.coachReply}>{turn.decision.coach_reply}</p><div className={styles.assessmentGrid}>{turn.decision.assessments.map((item) => <div className={styles.assessment} key={item.key}><strong>{COACHING_DIMENSION_LABELS[item.key] ?? item.key}{item.level ? ` · ${item.level}/5` : " · 证据不足"}</strong><p>{item.feedback}</p>{item.evidence_quote && <blockquote>{item.evidence_quote}</blockquote>}</div>)}</div></article>)}
          {session.current_question && <div className={styles.questionBlock}><span>{latest?.decision.action === "retry" ? "请重新组织" : latest ? "继续追问" : "训练题目"}</span><p>{session.current_question}</p></div>}
          {session.status === "completed" && <div className={styles.questionBlock}><span><CheckCircle2 size={14} /> 本次结论</span><p>{latest?.decision.summary}</p></div>}
        </div>
        {session.status === "planned" ? <div className={styles.composer}>{error && <p className={styles.error}>{error}</p>}<button className={`${styles.primary} ${styles.full}`} disabled={submitting} onClick={start}>开始训练 <ArrowRight size={16} /></button></div> : session.status === "active" && <form className={styles.composer} onSubmit={submit}><textarea value={answer} maxLength={20000} onChange={(event) => { setAnswer(event.target.value); setAnswerMode("text"); }} placeholder="按真实面试节奏完整回答，不需要追求一次说完美。" />{(error || voice.error) && <p className={styles.error}>{error || voice.error}</p>}<div className={styles.composerActions}><span>{voice.status === "listening" ? `正在录音 ${voice.seconds} 秒` : voice.status === "recognizing" ? "正在整理转写" : `${answer.length} / 20000`}</span><div className={styles.composerButtons}>{session.channel === "voice" && (voice.status === "listening" ? <button className={styles.secondary} type="button" onClick={() => void voice.stop()}><Square size={14} />停止</button> : <button className={styles.secondary} disabled={voice.status !== "idle" || submitting} type="button" onClick={() => void voice.start()}><Mic size={15} />语音回答</button>)}<button className={styles.primary} disabled={submitting || voice.status !== "idle" || !answer.trim()} type="submit">{submitting ? <><LoaderCircle className="spin" size={16} />正在分析回答</> : <>提交回答 <ArrowRight size={16} /></>}</button></div></div></form>}
      </section>
      <aside className={styles.roomSide}><h3>本次观察维度</h3><div className={styles.dimensionList}>{session.task.dimensions.map((item) => <span key={item}>{COACHING_DIMENSION_LABELS[item] ?? item}</span>)}</div><p>评价只依据你的回答证据。没有覆盖到的维度会标记为证据不足。</p>{session.status === "completed" && <Link href={`/training/new?mode=${session.mode}`} className={`${styles.secondary} ${styles.full}`}><RotateCcw size={15} />再练一次</Link>}</aside>
    </div>
  </main>;
}

"use client";

import { ArrowLeft, ArrowRight, Clock3, LoaderCircle, Target } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { COACHING_DIMENSION_LABELS, COACHING_MODE_LABELS, CoachingMode, CoachingSession, coachingSessionSchema } from "@/lib/coaching";

import styles from "./training.module.css";

export function CoachingSetup({ mode }: { mode: CoachingMode }) {
  const router = useRouter();
  const [role, setRole] = useState("AI 应用开发工程师");
  const [goal, setGoal] = useState("");
  const [channel, setChannel] = useState<"text" | "voice">("text");
  const [session, setSession] = useState<CoachingSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function create(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError("");
    try {
      const response = await fetch("/api/coaching-sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode, channel, target_role: role, training_goal: goal, source_ids: [] }) });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "训练任务生成失败");
      const parsed = coachingSessionSchema.safeParse(payload);
      if (!parsed.success) throw new Error("训练服务返回了无效任务");
      setSession(parsed.data);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "训练任务生成失败"); } finally { setLoading(false); }
  }

  async function start() {
    if (!session) return; setLoading(true); setError("");
    try {
      const response = await fetch(`/api/coaching-sessions/${session.id}/start`, { method: "POST" });
      if (!response.ok) { const payload: unknown = await response.json(); throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "训练暂时无法开始"); }
      router.push(`/training/${session.id}`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "训练暂时无法开始"); setLoading(false); }
  }

  return <main className={styles.page}>
    <Link href="/training" className="back-link"><ArrowLeft size={15} />返回训练中心</Link>
    <header className={styles.intro}><div><p className="eyebrow">{COACHING_MODE_LABELS[mode]}</p><h1>设定本次训练目标</h1><p>训练教练会先生成任务，你确认后再正式开始。</p></div></header>
    <div className={styles.setupLayout}>
      <form className={styles.form} onSubmit={create}>
        <label className={styles.field}><span>目标岗位</span><input value={role} maxLength={150} onChange={(event) => setRole(event.target.value)} required /></label>
        <label className={styles.field}><span>本次重点</span><textarea value={goal} maxLength={500} onChange={(event) => setGoal(event.target.value)} placeholder={mode === "structured_expression" ? "例如：项目介绍容易说得散，想练习结论先行" : "例如：技术方案很熟，但不清楚如何连接业务指标"} /></label>
        <fieldset className={styles.channelChoice}><legend>回答方式</legend><button type="button" className={channel === "text" ? styles.selected : ""} onClick={() => setChannel("text")}>文字</button><button type="button" className={channel === "voice" ? styles.selected : ""} onClick={() => setChannel("voice")}>语音</button></fieldset>
        {error && <p className={styles.error}>{error}</p>}
        <button className={`${styles.primary} ${styles.full}`} disabled={loading || !role.trim()} type="submit">{loading ? <><LoaderCircle className="spin" size={16} />正在生成训练任务</> : <>生成训练任务 <ArrowRight size={16} /></>}</button>
      </form>
      <aside className={styles.preview} aria-live="polite">
        {!session ? <><span className={styles.modeIcon}><Target size={20} /></span><h2>任务将在这里确认</h2><p>生成后可以先检查训练目标、场景、时长和评价维度。</p></> : <><p className="eyebrow">任务已生成</p><h2>{session.task.title}</h2><p>{session.task.objective}</p><dl><div><dt>预计时长</dt><dd><Clock3 size={13} /> {session.task.estimated_minutes} 分钟</dd></div><div><dt>训练形式</dt><dd>{session.channel === "voice" ? "语音对话" : "文字对话"}</dd></div></dl><p>{session.task.scenario}</p><div className={styles.dimensionList}>{session.task.dimensions.map((item) => <span key={item}>{COACHING_DIMENSION_LABELS[item] ?? item}</span>)}</div><button className={`${styles.primary} ${styles.full}`} type="button" disabled={loading} onClick={start}>确认并开始 <ArrowRight size={16} /></button></>}
      </aside>
    </div>
  </main>;
}

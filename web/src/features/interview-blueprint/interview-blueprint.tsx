"use client";

import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, GripVertical, Lightbulb, LoaderCircle, RefreshCw, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { PageIntro, PageShell, StatusBadge } from "@/components/page-shell";
import { REVIEW_MATERIAL_STORAGE_KEY, reviewMaterialSchema } from "@/lib/document-parse";
import { INTERVIEW_SESSION_STORAGE_KEY, InterviewSessionData, interviewSessionSchema } from "@/lib/interview-session";
import { trainingContextLabels } from "@/lib/training-context";
import { InterviewFlowProgress } from "@/features/interview-flow/flow-progress";
import { Button } from "@/components/ui/button";

function errorMessage(payload: unknown, fallback: string) {
  const detail = typeof payload === "object" && payload && "detail" in payload && typeof payload.detail === "string" ? payload.detail : fallback;
  const requestId = typeof payload === "object" && payload && "request_id" in payload && typeof payload.request_id === "string" ? payload.request_id : "";
  return requestId ? `${detail}（请求编号：${requestId}）` : detail;
}

export function InterviewBlueprint() {
  const [session, setSession] = useState<InterviewSessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryKey, setRetryKey] = useState(0);
  const context = session ? trainingContextLabels(session) : null;

  useEffect(() => {
    let active = true;
    async function generate() {
      const raw = sessionStorage.getItem(REVIEW_MATERIAL_STORAGE_KEY);
      if (!raw) throw new Error("没有找到已校正的训练材料，请从第一步重新开始。");
      let material;
      try {
        material = reviewMaterialSchema.parse(JSON.parse(raw));
      } catch {
        throw new Error("已校正的训练材料格式无效，请重新准备材料。");
      }
      if (!material.draftId) throw new Error("当前材料尚未保存到账号，请登录后重新完成材料准备。");
      const cachedRaw = sessionStorage.getItem(INTERVIEW_SESSION_STORAGE_KEY);
      if (cachedRaw) {
        try {
          const cached = interviewSessionSchema.parse(JSON.parse(cachedRaw));
          if (cached.draft_id === material.draftId) {
            if (active) setSession(cached);
            return;
          }
        } catch {
          sessionStorage.removeItem(INTERVIEW_SESSION_STORAGE_KEY);
        }
      }
      const response = await fetch("/api/interview-sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ draft_id: material.draftId }) });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "面试计划生成失败"));
      const parsed = interviewSessionSchema.parse(payload);
      sessionStorage.setItem(INTERVIEW_SESSION_STORAGE_KEY, JSON.stringify(parsed));
      if (active) setSession(parsed);
    }
    void generate().catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "面试计划生成失败"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retryKey]);

  return <PageShell active="new"><main className="content-container blueprint-page">
    <Link href="/review" className="back-link"><ArrowLeft size={15} />返回校正材料</Link>
    <PageIntro eyebrow="步骤 3 / 3 · 面试蓝图" title={session ? "确认今天要练什么" : "确认面试蓝图"} description={session?.summary} actions={session ? <StatusBadge tone="success"><CheckCircle2 size={13} />计划已保存</StatusBadge> : undefined} />
    <InterviewFlowProgress current={3} />
    {loading ? <section className="blueprint-generating" aria-live="polite"><LoaderCircle className="spin" size={20} /><div><strong>正在生成面试计划</strong><p>正在根据材料安排阶段与时长，完成后自动显示蓝图。</p></div></section> : error ? <section className="flow-error-state" role="alert"><AlertTriangle size={22} /><div><h2>无法生成面试计划</h2><p>{error}</p></div><div className="flow-error-actions"><Button type="button" onClick={() => { setError(""); setLoading(true); setRetryKey((value) => value + 1); }}><RefreshCw size={15} />重试生成</Button><Button asChild variant="secondary"><Link href="/setup"><ArrowLeft size={15} />检查材料</Link></Button></div></section> : session && <div className="blueprint-layout">
      <section className="phase-list" aria-label="面试阶段">{session.phases.map((phase, index) => <article className="phase-card" key={phase.name}><GripVertical size={18} className="drag-handle" /><span className="phase-number">{String(index + 1).padStart(2, "0")}</span><div className="phase-card-content"><div><span className="phase-kicker">阶段 {index + 1} · {phase.question_count} 道主问题</span><h2>{phase.name}</h2></div><div className="skill-tags">{phase.skills.map((skill) => <span key={skill}>{skill}</span>)}</div></div><div className="phase-time"><strong>{phase.minutes}</strong><span>分钟</span></div></article>)}<div className="blueprint-note"><ShieldCheck size={18} /><p><strong>问题仍保持隐藏。</strong>面试官会按计划逐题提问，并根据你的回答决定追问方向。</p></div></section>
      <aside className="blueprint-summary"><div className="summary-top"><span>{context?.type}</span><StatusBadge>{session.mode === "normal" ? "标准模式" : session.mode}</StatusBadge></div><strong className="duration-number">{session.duration_minutes}</strong><span className="duration-unit">分钟</span><dl>{session.target_company && <div><dt>目标公司</dt><dd>{session.target_company}</dd></div>}<div><dt>目标岗位</dt><dd>{session.target_role}</dd></div><div><dt>职级 / 轮次</dt><dd>{context?.level} · {context?.round}</dd></div><div><dt>考察阶段</dt><dd>{session.phases.length} 个</dd></div><div><dt>主问题</dt><dd>{session.phases.reduce((total, phase) => total + phase.question_count, 0)} 道</dd></div><div><dt>面试风格</dt><dd>压力 {session.pressure_level} · 深度 {session.depth_level} · 引导 {session.guidance_level}</dd></div>{session.training_focus && <div><dt>复训重点</dt><dd>{session.training_focus}</dd></div>}<div><dt>计划版本</dt><dd>{session.prompt_version}</dd></div></dl><div className="coach-tip"><Lightbulb size={18} /><p>{session.summary}</p></div><Button asChild className="w-full" size="lg"><Link href={`/interview?session=${session.id}`}>进入面试等候室 <ArrowRight size={17} /></Link></Button><p className="action-caption">先检查摄像头和麦克风，再正式开始</p></aside>
    </div>}
  </main></PageShell>;
}

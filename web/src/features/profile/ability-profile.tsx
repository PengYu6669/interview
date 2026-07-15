"use client";

import {
  ArrowRight,
  CandlestickChart,
  FileChartColumn,
  LoaderCircle,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PageIntro } from "@/components/page-shell";
import { AbilityProfileData, abilityProfileSchema } from "@/lib/ability-profile";
import { COACHING_DIMENSION_LABELS, COACHING_MODE_LABELS } from "@/lib/coaching";
import {
  RETRAINING_FOCUS_STORAGE_KEY,
  serializeRetrainingContext,
} from "@/lib/document-parse";
import { interviewReportSchema } from "@/lib/interview-report";
import { AbilityKline } from "./ability-kline";

type SkillItem = AbilityProfileData["skills"][number];
type SortMode = "priority" | "score" | "confidence" | "trend";

const SORT_OPTIONS: Array<{ value: SortMode; label: string }> = [
  { value: "priority", label: "建议顺序" },
  { value: "score", label: "能力分" },
  { value: "confidence", label: "可信度" },
  { value: "trend", label: "变化" },
];

export function AbilityProfile() {
  const router = useRouter();
  const [profile, setProfile] = useState<AbilityProfileData | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("priority");
  const [retrainingKey, setRetrainingKey] = useState("");
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    let active = true;
    void fetch("/api/profile", { cache: "no-store" })
      .then(async (response) => {
        const payload: unknown = await response.json();
        if (!response.ok) throw new Error(errorMessage(payload, "能力画像读取失败"));
        if (active) setProfile(abilityProfileSchema.parse(payload));
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "能力画像读取失败");
      });
    return () => {
      active = false;
    };
  }, []);

  const sortedSkills = useMemo(() => {
    const skills = [...(profile?.skills ?? [])];
    if (sortMode === "score") return skills.sort((left, right) => right.score - left.score);
    if (sortMode === "confidence") return skills.sort((left, right) => right.confidence - left.confidence);
    if (sortMode === "trend") return skills.sort((left, right) => right.trend - left.trend);
    return skills.sort((left, right) => left.score - right.score || left.confidence - right.confidence);
  }, [profile?.skills, sortMode]);

  if (!profile && !error) return <main className="content-container"><section className="profile-loading"><LoaderCircle className="spin" size={26} /><strong>正在汇总训练证据</strong></section></main>;

  async function startRetraining({
    key,
    focus,
    sourceSessionId,
    improvement,
  }: {
    key: string;
    focus: string;
    sourceSessionId: string;
    improvement?: { skill: string; title: string };
  }) {
    setRetrainingKey(key);
    setActionError("");
    try {
      const response = await fetch(
        `/api/interview-sessions/${encodeURIComponent(sourceSessionId)}/report`,
        { cache: "no-store" },
      );
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "来源报告读取失败"));
      const report = interviewReportSchema.parse(payload);
      const mode = report.mode === "relaxed" || report.mode === "stress" ? report.mode : "normal";
      sessionStorage.setItem(RETRAINING_FOCUS_STORAGE_KEY, serializeRetrainingContext({
        focus,
        source_session_id: sourceSessionId,
        target_role: report.target_role,
        target_company: report.target_company,
        target_level: report.target_level,
        interview_round: report.interview_round,
        interview_type: "weak_area",
        mode,
        pressure_level: report.pressure_level,
        depth_level: report.depth_level,
        guidance_level: report.guidance_level,
        improvements: improvement ? [improvement] : [],
      }));
      router.push("/setup");
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "暂时无法创建复训");
      setRetrainingKey("");
    }
  }

  const latestPoint = profile?.kline.at(-1);
  const previousPoint = profile && profile.kline.length > 1 ? profile.kline.at(-2) : null;
  const latestChange = latestPoint && previousPoint ? latestPoint.close - previousPoint.close : null;

  return <main className="content-container profile-page">
    <PageIntro eyebrow="能力画像" title="看清能力波动，而不只看一次总分" description="基于已保存报告的证据覆盖率和置信度，观察能力区间、收盘表现与长期变化。" actions={<Link href="/setup" className="primary-cta">开始新训练 <ArrowRight size={16} /></Link>} />
    {error ? <section className="matrix-empty" role="alert"><Target size={21} /><span>{error}</span></section> : profile && <>
      <section className="profile-summary-strip"><div><span>有效报告</span><strong>{profile.report_count}</strong></div><div><span>平均表现</span><strong>{profile.average_score ?? "--"}</strong></div><div><span>平均证据覆盖</span><strong>{profile.average_coverage === null ? "--" : `${profile.average_coverage}%`}</strong></div><div><span>最近变化</span><strong className={latestChange === null ? "" : latestChange > 0 ? "positive" : latestChange < 0 ? "negative" : ""}>{latestChange === null ? "--" : latestChange > 0 ? `+${latestChange}` : latestChange}</strong></div></section>
      <section className="profile-grid">
        <div className="trend-panel kline-panel"><div className="panel-heading"><div><span>能力增长 K 线</span><small>透明度反映报告置信度，点击蜡烛可回看对应报告</small></div><CandlestickChart size={19} /></div><AbilityKline points={profile.kline.map((point) => ({ ...point, date: new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(new Date(point.date)) }))} /></div>
        <aside className={`recommendation-panel ${profile.next_training ? "" : "empty-recommendation"}`}><Target size={21} /><span>建议复训主题</span><h2>{profile.next_training ? "下一场优先训练" : "等待训练证据"}</h2><p>{profile.next_training ?? "至少生成一份有回答证据的报告后，系统才会形成复训建议。"}</p>{profile.next_training && latestPoint ? <button type="button" disabled={Boolean(retrainingKey)} onClick={() => void startRetraining({ key: "overall", focus: profile.next_training!, sourceSessionId: latestPoint.session_id })}>{retrainingKey === "overall" ? <LoaderCircle className="spin" size={14} /> : <Target size={14} />}创建综合复训</button> : <Link href="/history">查看训练记录 <ArrowRight size={14} /></Link>}</aside>
      </section>
      <section className="profile-evidence-note"><ShieldCheck size={18} /><div><strong>分数不等于确定结论</strong><span>能力分按证据覆盖率和单项置信度加权；可信度低于 40% 表示样本仍不足，优先补充训练证据。</span></div></section>
      {actionError && <p className="profile-action-error" role="alert">{actionError}</p>}
      <section className="ability-matrix-section coaching-ability-section">
        <div className="ability-matrix-header"><div><h2>专项训练能力</h2><p>{profile.coaching.session_count ? `共 ${profile.coaching.session_count} 次训练，连续训练 ${profile.coaching.current_streak_days} 天；同一维度连续三次达到有效标准才标记稳定掌握` : "完成结构化表达或业务 Sense 训练后，这里会形成独立能力观察"}</p></div>{profile.coaching.next_mode && <Link href={`/training/new?mode=${profile.coaching.next_mode}&difficulty=${profile.coaching.next_difficulty}&focus=${encodeURIComponent(profile.coaching.next_focus ?? "")}`} className="secondary-button"><Target size={14} />练习最弱项</Link>}</div>
        {profile.coaching.skills.length ? <div className="matrix-grid">{profile.coaching.skills.map((item) => <article key={item.dimension}><span className="matrix-score">{item.score}</span><div className="skill-summary"><div><h3>{COACHING_DIMENSION_LABELS[item.dimension] ?? item.dimension}</h3><span className="confidence-label">{COACHING_MODE_LABELS[item.mode]}</span></div><p>{item.evidence_count} 条回答证据 · {item.session_count} 次独立训练 · 可信度 {Math.round(item.confidence * 100)}%</p><small>{item.latest_feedback}</small></div><span className={`matrix-trend ${item.mastery_status === "stable" ? "up" : item.mastery_status === "improving" ? "flat" : "down"}`}>{item.mastery_status === "stable" ? "稳定掌握" : item.mastery_status === "improving" ? `正在进步${item.trend > 0 ? ` +${item.trend}` : ""}` : "继续练习"}</span><div className="skill-actions"><Link href={`/training/${item.source_session_id}`} title="查看来源训练" aria-label={`查看 ${COACHING_DIMENSION_LABELS[item.dimension] ?? item.dimension} 的来源训练`}><FileChartColumn size={14} /></Link><Link href={`/training/new?mode=${item.mode}&difficulty=${profile.coaching.next_difficulty}&focus=${encodeURIComponent(item.latest_feedback)}`} className="coaching-retrain"><Target size={13} />再练一次</Link></div></article>)}</div> : <div className="matrix-empty"><Target size={21} /><span>{profile.coaching.session_count ? "当前训练还没有足够的有效回答证据" : "还没有专项训练记录"}</span><Link href="/training">进入训练中心 <ArrowRight size={14} /></Link></div>}
      </section>
      <section className="ability-matrix-section">
        <div className="ability-matrix-header"><div><h2>技术能力矩阵</h2><p>未考察能力不会被记为低分，点击来源可回到最近一次对应报告</p></div>{sortedSkills.length > 1 && <div className="ability-sort" aria-label="能力排序">{SORT_OPTIONS.map((option) => <button key={option.value} type="button" aria-pressed={sortMode === option.value} className={sortMode === option.value ? "active" : ""} onClick={() => setSortMode(option.value)}>{option.label}</button>)}</div>}</div>
        {sortedSkills.length ? <div className="matrix-grid">{sortedSkills.map((item) => <SkillRow item={item} key={item.skill} loading={retrainingKey === item.skill} disabled={Boolean(retrainingKey)} onRetrain={() => void startRetraining({ key: item.skill, focus: item.training_focus, sourceSessionId: item.source_session_id, improvement: { skill: item.skill, title: item.training_focus } })} />)}</div> : <div className="matrix-empty"><Target size={21} /><span>当前报告还没有可聚合的能力证据</span></div>}
      </section>
    </>}
  </main>;
}

function SkillRow({
  item,
  loading,
  disabled,
  onRetrain,
}: {
  item: SkillItem;
  loading: boolean;
  disabled: boolean;
  onRetrain: () => void;
}) {
  const confidence = Math.round(item.confidence * 100);
  const confidenceLabel = confidence >= 70 ? "证据较稳定" : confidence >= 40 ? "初步判断" : "样本不足";
  return <article><span className="matrix-score">{item.score}</span><div className="skill-summary"><div><h3>{item.skill}</h3><span className={`confidence-label ${confidence < 40 ? "low" : confidence >= 70 ? "high" : ""}`}>{confidenceLabel}</span></div><p>{item.evidence_count} 条证据 · {item.report_count} 场训练 · 可信度 {confidence}%</p><small>{item.training_focus}</small></div><span className={`matrix-trend ${item.trend > 0 ? "up" : item.trend < 0 ? "down" : "flat"}`}>{item.trend > 0 ? <TrendingUp size={14} /> : item.trend < 0 ? <TrendingDown size={14} /> : null}{item.trend > 0 ? `+${item.trend}` : item.trend === 0 ? "持平" : item.trend}</span><div className="skill-actions"><Link href={`/report?session=${item.source_session_id}`} title="查看来源报告" aria-label={`查看 ${item.skill} 的来源报告`}><FileChartColumn size={14} /></Link><button type="button" disabled={disabled} onClick={onRetrain}>{loading ? <LoaderCircle className="spin" size={13} /> : <Target size={13} />}专项复训</button></div></article>;
}

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload
    ? String(payload.detail)
    : fallback;
}

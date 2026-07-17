"use client";

import {
  ArrowRight,
  ChartNoAxesColumnIncreasing,
  FileChartColumn,
  LoaderCircle,
  ShieldCheck,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PageIntro } from "@/components/page-shell";
import { EvidenceChain } from "@/components/evidence-chain";
import { AbilityProfileData, abilityProfileSchema } from "@/lib/ability-profile";
import { COACHING_DIMENSION_LABELS, COACHING_MODE_LABELS } from "@/lib/coaching";
import { prepareInterviewRetraining } from "@/lib/retraining";
import { AbilityKline } from "./ability-kline";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";

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
      await prepareInterviewRetraining({ sourceSessionId, focus, improvement });
      router.push("/setup");
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "暂时无法创建复训");
      setRetrainingKey("");
    }
  }

  const latestPoint = profile?.kline.at(-1);
  const evidenceStability = latestPoint ? Math.round(latestPoint.confidence * 100) : null;

  return <main className="content-container profile-page">
    <PageIntro eyebrow="能力画像" title="看清哪些能力正在形成稳定证据" description="每场题目和难度可能不同，因此场次总分不直接作为成长结论；同一能力的原句证据、样本量和趋势才用于判断。" actions={<Button asChild><Link href="/setup">开始新训练 <ArrowRight size={16} /></Link></Button>} />
    {error ? <section className="matrix-empty" role="alert"><Target size={21} /><span>{error}</span></section> : profile && <>
      <section className="profile-summary-strip"><div><span>有效报告</span><strong>{profile.report_count}</strong></div><div><span>最近场次表现</span><strong>{latestPoint?.close ?? "--"}</strong></div><div><span>平均证据覆盖</span><strong>{profile.average_coverage === null ? "--" : `${profile.average_coverage}%`}</strong></div><div><span>最近证据稳定度</span><strong>{evidenceStability === null ? "--" : `${evidenceStability}%`}</strong></div></section>
      <section className="profile-grid">
        <div className="trend-panel kline-panel"><div className="panel-heading"><div><span>训练表现记录</span><small>总分仅描述当场表现；点击记录回看题目、难度和回答证据</small></div><ChartNoAxesColumnIncreasing size={19} /></div><AbilityKline points={profile.kline.map((point) => ({ ...point, date: new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(new Date(point.date)) }))} /></div>
        <aside className={`recommendation-panel ${profile.next_training ? "" : "empty-recommendation"}`}><Target size={21} /><span>建议复训主题</span><h2>{profile.next_training ? "下一场优先训练" : "等待训练证据"}</h2><p>{profile.next_training ?? "至少生成一份有回答证据的报告后，系统才会形成复训建议。"}</p>{profile.next_training && latestPoint ? <button type="button" disabled={Boolean(retrainingKey)} onClick={() => void startRetraining({ key: "overall", focus: profile.next_training!, sourceSessionId: latestPoint.session_id })}>{retrainingKey === "overall" ? <LoaderCircle className="spin" size={14} /> : <Target size={14} />}创建综合复训</button> : <Link href="/history">查看训练记录 <ArrowRight size={14} /></Link>}</aside>
      </section>
      <section className="profile-evidence-note"><ShieldCheck size={18} /><div><strong>分数不等于确定结论</strong><span>能力分按证据覆盖率和单项置信度加权；可信度低于 40% 表示样本仍不足，优先补充训练证据。</span></div></section>
      {actionError && <p className="profile-action-error" role="alert">{actionError}</p>}
      <section className="ability-matrix-section coaching-ability-section">
        <div className="ability-matrix-header"><div><h2>专项训练能力</h2><p>{profile.coaching.session_count ? `共 ${profile.coaching.session_count} 次训练，连续训练 ${profile.coaching.current_streak_days} 天；同一维度连续三次达到有效标准才标记稳定掌握` : "完成结构化表达或业务 Sense 训练后，这里会形成独立能力观察"}</p></div>{profile.coaching.next_mode && <Link href={`/training/new?mode=${profile.coaching.next_mode}&difficulty=${profile.coaching.next_difficulty}&focus=${encodeURIComponent(profile.coaching.next_focus ?? "")}`} className="secondary-button"><Target size={14} />练习最弱项</Link>}</div>
        {profile.coaching.skills.length ? <div className="matrix-grid">{profile.coaching.skills.map((item) => <article key={item.dimension}><span className="matrix-score">{item.score}</span><div className="skill-summary"><div><h3>{COACHING_DIMENSION_LABELS[item.dimension] ?? item.dimension}</h3><span className="confidence-label">{COACHING_MODE_LABELS[item.mode]}</span></div><p>{item.evidence_count} 条回答证据 · {item.session_count} 次独立训练 · 可信度 {Math.round(item.confidence * 100)}%</p><small>{item.latest_feedback}</small></div><span className={`matrix-trend ${item.mastery_status === "stable" ? "up" : item.mastery_status === "improving" ? "flat" : "down"}`}>{item.mastery_status === "stable" ? "稳定掌握" : item.mastery_status === "improving" ? `正在进步${item.trend > 0 ? ` +${item.trend}` : ""}` : "继续练习"}</span><div className="skill-actions"><Link href={`/training/${item.source_session_id}`} title="查看来源训练" aria-label={`查看 ${COACHING_DIMENSION_LABELS[item.dimension] ?? item.dimension} 的来源训练`}><FileChartColumn size={14} /></Link><Link href={`/training/new?mode=${item.mode}&difficulty=${profile.coaching.next_difficulty}&focus=${encodeURIComponent(item.latest_feedback)}`} className="coaching-retrain"><Target size={13} />再练一次</Link></div></article>)}</div> : <div className="matrix-empty"><Target size={21} /><span>{profile.coaching.session_count ? "当前训练还没有足够的有效回答证据" : "还没有专项训练记录"}</span><Link href="/training">进入训练中心 <ArrowRight size={14} /></Link></div>}
      </section>
      <section className="ability-matrix-section">
        <div className="ability-matrix-header"><div><h2>技术能力矩阵</h2><p>未考察能力不会被记为低分，点击来源可回到最近一次对应报告</p></div>{sortedSkills.length > 1 && <SegmentedControl label="能力排序" value={sortMode} onValueChange={setSortMode} options={SORT_OPTIONS} />}</div>
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
  const trendLabel = item.trend > 0 ? `提升 ${item.trend} 分` : item.trend < 0 ? `下降 ${Math.abs(item.trend)} 分` : "近期持平";
  return <EvidenceChain conclusion={`${item.skill} · 当前 ${item.score} 分`} evidence={item.evidence_quote} basis={`${item.evidence_count} 条证据来自 ${item.report_count} 场训练，${trendLabel}。分数按证据覆盖与置信度加权，来源报告保留完整上下文。`} confidence={item.confidence} action={item.training_focus} meta={confidenceLabel} controls={<div className="skill-evidence-controls"><Link href={`/report?session=${item.source_session_id}`} title="查看来源报告" aria-label={`查看 ${item.skill} 的来源报告`}><FileChartColumn size={14} />来源</Link><button type="button" disabled={disabled} onClick={onRetrain}>{loading ? <LoaderCircle className="spin" size={13} /> : <Target size={13} />}专项复训</button></div>} tone={confidence < 40 ? "warning" : item.trend > 0 ? "positive" : "neutral"} />;
}

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload
    ? String(payload.detail)
    : fallback;
}

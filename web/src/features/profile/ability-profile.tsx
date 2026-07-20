"use client";

import {
  ArrowRight,
  ChevronDown,
  FileChartColumn,
  LoaderCircle,
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

  if (!profile && !error) return <main className="content-container"><section className="profile-loading"><LoaderCircle className="spin" size={26} /><strong>正在汇总训练表现</strong></section></main>;

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
  const prioritySkill = sortedSkills[0];

  return (
    <main className="content-container profile-page">
      <PageIntro
        title="能力画像"
        actions={<Button asChild><Link href="/setup">开始新训练 <ArrowRight size={16} /></Link></Button>}
      />
      {error ? (
        <section className="mt-8 flex min-h-40 items-center justify-center gap-3 border-y border-[var(--line)] text-sm text-[var(--muted)]" role="alert">
          <Target size={20} /><span>{error}</span>
        </section>
      ) : profile && (
        <>
          <section className="mt-7 grid border-y border-[var(--line)] md:grid-cols-[minmax(0,1fr)_220px]">
            <div className="py-6 pr-0 md:pr-8">
              <span className="text-xs font-semibold text-[var(--accent-dark)]">下一步</span>
              <h2 className="mt-2 text-xl font-semibold text-[var(--ink)]">
                {prioritySkill ? `优先提升：${prioritySkill.skill}` : profile.next_training ? "优先完成一次针对性训练" : "先积累一份有效报告"}
              </h2>
              {(prioritySkill?.training_focus || profile.next_training) && <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
                {prioritySkill?.training_focus ?? profile.next_training}
              </p>}
              <div className="mt-5 flex flex-wrap gap-2">
                {prioritySkill && latestPoint ? (
                  <Button
                    type="button"
                    disabled={Boolean(retrainingKey)}
                    onClick={() => void startRetraining({
                      key: prioritySkill.skill,
                      focus: prioritySkill.training_focus,
                      sourceSessionId: prioritySkill.source_session_id,
                      improvement: { skill: prioritySkill.skill, title: prioritySkill.training_focus },
                    })}
                  >
                    {retrainingKey === prioritySkill.skill ? <LoaderCircle className="spin" size={15} /> : <Target size={15} />}
                    训练这个短板
                  </Button>
                ) : (
                  <Button asChild><Link href="/setup">开始一次训练 <ArrowRight size={15} /></Link></Button>
                )}
                <Button asChild variant="secondary"><Link href="/history">查看训练记录</Link></Button>
              </div>
            </div>
            <div className="grid grid-cols-3 border-t border-[var(--line)] py-5 md:grid-cols-1 md:border-l md:border-t-0 md:pl-7">
              <Metric label="有效报告" value={profile.report_count} />
              <Metric label="训练覆盖" value={profile.average_coverage === null ? "--" : `${profile.average_coverage}%`} />
              <Metric label="表现稳定度" value={evidenceStability === null ? "--" : `${evidenceStability}%`} />
            </div>
          </section>

          {actionError && <p className="mt-4 border-l-2 border-[var(--danger)] bg-[var(--danger-bg)] px-3 py-2 text-sm text-[var(--danger)]" role="alert">{actionError}</p>}

          <section className="mt-9">
            <div className="flex items-end justify-between gap-4">
              <h2 className="text-lg font-semibold">能力概览</h2>
              {sortedSkills.length > 1 && <SegmentedControl label="能力排序" value={sortMode} onValueChange={setSortMode} options={SORT_OPTIONS} />}
            </div>
            {sortedSkills.length ? (
              <div className="mt-5 divide-y divide-[var(--line)] border-y border-[var(--line)]">
                {sortedSkills.slice(0, 3).map((item) => <SkillSummary key={item.skill} item={item} />)}
              </div>
            ) : (
              <div className="mt-5 py-10 text-center text-sm text-[var(--muted)]">当前还没有足够的技术能力记录</div>
            )}
          </section>

          <details className="group mt-9 border-y border-[var(--line)] py-1">
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 py-3 text-sm font-semibold">
              训练趋势与场次记录
              <ChevronDown className="transition-transform group-open:rotate-180" size={18} />
            </summary>
            <div className="pb-6">
              <AbilityKline points={profile.kline.map((point) => ({ ...point, date: new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(new Date(point.date)) }))} />
            </div>
          </details>

          <details className="group border-b border-[var(--line)] py-1">
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 py-3 text-sm font-semibold">
              完整能力表现 <span className="ml-auto text-xs font-normal text-[var(--muted)]">{sortedSkills.length} 项技术能力 · {profile.coaching.skills.length} 项专项能力</span>
              <ChevronDown className="transition-transform group-open:rotate-180" size={18} />
            </summary>
            <div className="grid gap-8 pb-8">
              <section>
                <h3 className="text-sm font-semibold">专项训练</h3>
                {profile.coaching.skills.length ? (
                  <div className="mt-3 divide-y divide-[var(--line)] border-y border-[var(--line)]">
                    {profile.coaching.skills.map((item) => (
                      <div className="grid gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center" key={item.dimension}>
                        <div><strong className="text-sm">{COACHING_DIMENSION_LABELS[item.dimension] ?? item.dimension}</strong><p className="mt-1 text-xs leading-5 text-[var(--muted)]">{item.latest_feedback}</p><small className="mt-1 block text-xs text-[var(--muted)]">{COACHING_MODE_LABELS[item.mode]} · {item.evidence_count} 次记录 · 可信度 {Math.round(item.confidence * 100)}%</small></div>
                        <Button asChild variant="secondary" size="sm"><Link href={`/training/new?mode=${item.mode}&difficulty=${profile.coaching.next_difficulty}&focus=${encodeURIComponent(item.latest_feedback)}`}><Target size={13} />再练一次</Link></Button>
                      </div>
                    ))}
                  </div>
                ) : <p className="mt-3 text-sm text-[var(--muted)]">还没有专项训练记录</p>}
              </section>
              <section>
                <h3 className="text-sm font-semibold">技术能力表现</h3>
                <div className="mt-3 grid gap-3">
                  {sortedSkills.map((item) => <SkillRow item={item} key={item.skill} loading={retrainingKey === item.skill} disabled={Boolean(retrainingKey)} onRetrain={() => void startRetraining({ key: item.skill, focus: item.training_focus, sourceSessionId: item.source_session_id, improvement: { skill: item.skill, title: item.training_focus } })} />)}
                </div>
              </section>
            </div>
          </details>
        </>
      )}
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="px-2 py-2 md:px-0"><span className="block text-xs text-[var(--muted)]">{label}</span><strong className="mt-1 block text-lg font-semibold text-[var(--ink)]">{value}</strong></div>;
}

function SkillSummary({ item }: { item: SkillItem }) {
  const confidence = Math.round(item.confidence * 100);
  return (
    <article className="grid gap-3 py-4 sm:grid-cols-[160px_minmax(0,1fr)_90px] sm:items-center">
      <div><strong className="text-sm">{item.skill}</strong><span className="mt-1 block text-xs text-[var(--muted)]">可信度 {confidence}%</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--bg-hover)]"><i className="block h-full bg-[var(--accent)]" style={{ width: `${Math.max(4, Math.min(100, item.score))}%` }} /></div>
      <div className="text-left sm:text-right"><strong className="text-base">{item.score}</strong><span className="ml-1 text-xs text-[var(--muted)]">分</span></div>
    </article>
  );
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
  const confidenceLabel = confidence >= 70 ? "表现较稳定" : confidence >= 40 ? "初步判断" : "样本不足";
  const trendLabel = item.trend > 0 ? `提升 ${item.trend} 分` : item.trend < 0 ? `下降 ${Math.abs(item.trend)} 分` : "近期持平";
  return <EvidenceChain conclusion={`${item.skill} · 当前 ${item.score} 分`} evidence={item.evidence_quote} basis={`${item.evidence_count} 次表现记录来自 ${item.report_count} 场训练，${trendLabel}。`} confidence={item.confidence} action={item.training_focus} meta={confidenceLabel} controls={<div className="skill-evidence-controls"><Link href={`/report?session=${item.source_session_id}`} title="查看训练复盘" aria-label={`查看 ${item.skill} 的训练复盘`}><FileChartColumn size={14} />复盘</Link><button type="button" disabled={disabled} onClick={onRetrain}>{loading ? <LoaderCircle className="spin" size={13} /> : <Target size={13} />}专项复训</button></div>} tone={confidence < 40 ? "warning" : item.trend > 0 ? "positive" : "neutral"} />;
}

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload
    ? String(payload.detail)
    : fallback;
}

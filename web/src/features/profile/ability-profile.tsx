"use client";

import {
  ArrowRight,
  LoaderCircle,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PageIntro } from "@/components/page-shell";
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
  const performanceStability = latestPoint ? Math.round(latestPoint.confidence * 100) : null;
  const prioritySkill = sortedSkills[0];

  return (
    <main className="content-container profile-page">
      <PageIntro
        title="能力画像"
        actions={<Button asChild><Link href="/setup">开始新训练 <ArrowRight size={16} /></Link></Button>}
      />
      {error ? (
        <section className="mt-8 flex min-h-40 items-center justify-center gap-3 rounded-lg bg-[var(--bg-subtle)] text-sm text-[var(--muted)]" role="alert">
          <Target size={20} /><span>{error}</span>
        </section>
      ) : profile && (
        <>
          <section className="profile-next-step mt-6 grid gap-6 rounded-lg bg-[var(--bg-subtle)] p-5 sm:p-6 md:grid-cols-[minmax(0,1fr)_220px] md:items-center">
            <div>
              <span className="text-xs font-semibold text-[var(--accent-dark)]">下一步</span>
              <h2 className="mt-2 text-xl font-semibold text-[var(--ink)] sm:text-2xl">
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
            <div className="grid grid-cols-3 gap-3 border-t border-[var(--border-default)] pt-4 md:grid-cols-1 md:border-l md:border-t-0 md:pl-6 md:pt-0">
              <Metric label="有效报告" value={profile.report_count} />
              <Metric label="训练覆盖" value={profile.average_coverage === null ? "暂无" : `${profile.average_coverage}%`} />
              <Metric label="表现稳定度" value={performanceStability === null ? "暂无" : `${performanceStability}%`} />
            </div>
          </section>

          {actionError && <p className="mt-4 border-l-2 border-[var(--danger)] bg-[var(--danger-bg)] px-3 py-2 text-sm text-[var(--danger)]" role="alert">{actionError}</p>}

          <section className="mt-10">
            <div className="flex items-end justify-between gap-4">
              <h2 className="text-lg font-semibold">能力概览</h2>
              {sortedSkills.length > 1 && <SegmentedControl label="能力排序" value={sortMode} onValueChange={setSortMode} options={SORT_OPTIONS} />}
            </div>
            {sortedSkills.length ? (
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {sortedSkills.map((item) => <SkillSummary key={item.skill} item={item} />)}
              </div>
            ) : (
              <div className="mt-5 py-10 text-center text-sm text-[var(--muted)]">当前还没有足够的技术能力记录</div>
            )}
          </section>

          <section className="mt-10 profile-trend-section">
            <div className="flex items-start justify-between gap-4"><h2 className="text-lg font-semibold">训练趋势</h2><span className="text-xs text-[var(--muted)]">{profile.kline.length} 场</span></div>
            <div className="mt-5"><AbilityKline points={profile.kline.map((point) => ({ ...point, date: new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(new Date(point.date)) }))} /></div>
          </section>

          {profile.coaching.skills.length > 0 && <section className="mt-10">
            <h2 className="text-lg font-semibold">专项训练</h2>
            <div className="mt-5 grid gap-3 md:grid-cols-2">{profile.coaching.skills.map((item) => <article className="rounded-lg border border-[var(--border-default)] bg-white p-4" key={item.dimension}><div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-semibold">{COACHING_DIMENSION_LABELS[item.dimension] ?? item.dimension}</h3><p className="mt-2 text-sm leading-6 text-[var(--muted)]">{item.latest_feedback}</p></div><span className="shrink-0 text-sm font-semibold">{item.score} 分</span></div><div className="mt-4 flex items-center justify-between gap-3"><span className="text-xs text-[var(--muted)]">{COACHING_MODE_LABELS[item.mode]} · 稳定度 {Math.round(item.confidence * 100)}%</span><Button asChild variant="secondary" size="sm"><Link href={`/training/new?mode=${item.mode}&difficulty=${profile.coaching.next_difficulty}&focus=${encodeURIComponent(item.latest_feedback)}`}><Target size={13} />再练一次</Link></Button></div></article>)}</div>
          </section>}
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
    <article className="rounded-lg border border-[var(--border-default)] bg-white p-4">
      <div className="flex items-center justify-between gap-3"><strong className="text-sm">{item.skill}</strong><span className="text-base font-semibold">{item.score}<span className="ml-1 text-xs font-normal text-[var(--muted)]">分</span></span></div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[var(--bg-hover)]"><i className="block h-full bg-[var(--ink)]" style={{ width: `${Math.max(4, Math.min(100, item.score))}%` }} /></div>
      <div className="mt-2 flex items-center justify-between gap-3 text-xs text-[var(--muted)]"><span>稳定度 {confidence}%</span><span>{item.trend > 0 ? `提升 ${item.trend} 分` : item.trend < 0 ? `下降 ${Math.abs(item.trend)} 分` : "近期持平"}</span></div>
    </article>
  );
}

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload
    ? String(payload.detail)
    : fallback;
}

"use client";

import { ArrowRight, Bot, BriefcaseBusiness, CheckCircle2, Clock3, ListTree, LoaderCircle, MessageSquareText, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { COACHING_MODE_LABELS, CoachingSummary, coachingSummarySchema } from "@/lib/coaching";
import { AbilityProfileData, abilityProfileSchema } from "@/lib/ability-profile";
import { type WeeklyPlanItem, weeklyPlanItemSchema } from "@/lib/career";
import { QUESTION_COACHING_SELECTION_KEY } from "@/lib/questions";
import { prepareInterviewRetraining } from "@/lib/retraining";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import styles from "./training.module.css";

const modes = [
  { href: "/setup", title: "模拟面试", description: "完整面试流程与语音实战", icon: MessageSquareText },
  { href: "/training/new?mode=structured_expression", title: "结构化表达", description: "结论、职责、取舍与结果", icon: ListTree },
  { href: "/training/new?mode=business_sense", title: "业务 Sense", description: "目标、指标、优先级与验证", icon: BriefcaseBusiness },
];

function localDate() {
  const date = new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function TrainingHub() {
  const router = useRouter();
  const [recent, setRecent] = useState<CoachingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<AbilityProfileData | null>(null);
  const [today, setToday] = useState<WeeklyPlanItem[]>([]);
  const [recommendationLoading, setRecommendationLoading] = useState(true);
  const [contextError, setContextError] = useState("");
  const [startingRecommendation, setStartingRecommendation] = useState(false);
  const [recommendationError, setRecommendationError] = useState("");

  useEffect(() => {
    let mounted = true;
    void fetch("/api/coaching-sessions", { cache: "no-store" }).then(async (response) => {
      if (!response.ok) return;
      const parsed = coachingSummarySchema.safeParse(await response.json());
      if (mounted && parsed.success) setRecent(parsed.data);
    }).finally(() => { if (mounted) setLoading(false); });
    void Promise.all([
      fetch("/api/profile", { cache: "no-store" }),
      fetch(`/api/career/today?date=${localDate()}`, { cache: "no-store" }),
    ]).then(async ([profileResponse, todayResponse]) => {
      const profilePayload: unknown = await profileResponse.json();
      const todayPayload: unknown = await todayResponse.json();
      const parsedProfile = profileResponse.ok ? abilityProfileSchema.safeParse(profilePayload) : null;
      const parsedToday = todayResponse.ok ? weeklyPlanItemSchema.array().safeParse(todayPayload) : null;
      if (!mounted) return;
      if (parsedProfile?.success) setProfile(parsedProfile.data);
      else setContextError("能力画像暂时无法读取，今日建议没有降级为基线训练。");
      if (parsedToday?.success) setToday(parsedToday.data);
    }).catch(() => {
      if (mounted) setContextError("训练计划与能力画像暂时无法读取，请稍后刷新页面。");
    }).finally(() => {
      if (mounted) setRecommendationLoading(false);
    });
    return () => { mounted = false; };
  }, []);

  async function startPlannedItem(item: WeeklyPlanItem) {
    if (item.task_type === "question_review" && item.question_id) {
      if (item.plan_id && item.status === "pending") {
        const response = await fetch(`/api/career/weekly-plan/${encodeURIComponent(item.plan_id)}/items/${encodeURIComponent(item.id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "in_progress" }) });
        if (!response.ok) {
          setRecommendationError("今日任务暂时无法同步，请稍后重试");
          return;
        }
      }
      const query = item.plan_id ? `?plan=${item.plan_id}&planItem=${item.id}` : "";
      router.push(item.question_slug ? `/questions/${item.question_slug}${query}` : "/questions");
      return;
    }
    if (item.coaching_mode) {
      if (item.question_id) {
        const framework = item.exercise_type === "prep_pitch" ? "prep" : "star";
        sessionStorage.setItem(QUESTION_COACHING_SELECTION_KEY, JSON.stringify({ questions: [{ id: item.question_id, title: item.title, framework }] }));
      }
      const query = new URLSearchParams({ mode: item.coaching_mode, difficulty: item.difficulty ?? "guided", focus: item.completion_criteria, planItem: item.id });
      router.push(`/training/new?${query.toString()}`);
      return;
    }
    router.push(item.task_type === "mock_interview" ? `/setup?planItem=${item.id}` : "/history?view=plan");
  }

  const primaryTask = today.find((item) => item.status !== "completed" && item.status !== "skipped");
  const remainingTasks = today.filter((item) => item.id !== primaryTask?.id);
  const coaching = profile?.coaching;
  const profileSourceSessionId = profile?.kline.at(-1)?.session_id;
  const nextTrainingHref = coaching?.next_mode
    ? `/training/new?mode=${coaching.next_mode}&difficulty=${coaching.next_difficulty}&focus=${encodeURIComponent(coaching.next_focus ?? "")}`
    : "/setup";
  const primaryTitle = primaryTask?.title ?? profile?.next_training ?? coaching?.next_focus ?? "完成一场基于真实经历的模拟面试";
  const primaryReason = primaryTask?.reason
    ?? (profile?.next_training ? `最近一场证据报告建议继续验证：${profile.next_training}` : coaching?.next_focus ? `专项训练画像建议继续验证：${coaching.next_focus}` : "还没有足够的历史证据，先完成一次基线训练。");
  const primaryMeta = primaryTask
    ? `${primaryTask.estimated_minutes} 分钟 · ${primaryTask.completion_criteria}`
    : profile?.next_training ? `30 分钟 · 基于最近 ${profile.report_count} 份有效报告` : coaching?.next_mode ? `10 分钟 · ${coaching.current_streak_days} 天连续训练 · ${coaching.next_difficulty === "guided" ? "有骨架" : coaching.next_difficulty === "assisted" ? "关键词提示" : "限时脱稿"}` : "30 分钟 · 建立第一份能力证据";

  async function startProfileRecommendation() {
    if (!profile?.next_training || !profileSourceSessionId) return;
    setStartingRecommendation(true);
    setRecommendationError("");
    try {
      await prepareInterviewRetraining({ sourceSessionId: profileSourceSessionId, focus: profile.next_training });
      router.push("/setup");
    } catch (caught) {
      setRecommendationError(caught instanceof Error ? caught.message : "暂时无法准备弱项复训");
    } finally {
      setStartingRecommendation(false);
    }
  }

  return <main className={styles.page}>
    <header className={styles.intro}>
      <div><p className="eyebrow">AI 面试教练</p><h1>今天只推进一个能力目标</h1><p>推荐来自已确认的求职计划、历史训练证据和待验证弱项；依据不足时，系统会明确从基线训练开始。</p></div>
    </header>
    {recommendationLoading ? <section className={styles.coachLoading} aria-live="polite"><LoaderCircle className="spin" size={18} /><div><strong>正在汇总今日训练上下文</strong><span>读取已确认计划、历史证据和待验证弱项</span></div></section> : contextError ? <section className={styles.coachLoading} role="alert"><Bot size={18} /><div><strong>今日建议读取失败</strong><span>{contextError}</span></div></section> : <section className={styles.coachBrief} aria-label="今日教练建议">
      <div className={styles.coachBriefMain}><span className={styles.coachIcon}><Bot size={22} /></span><div><Badge tone="accent">{primaryTask ? "来自本周计划" : profile?.next_training ? "来自最近证据报告" : coaching?.next_mode ? "来自专项训练画像" : "建立训练基线"}</Badge><h2>{primaryTitle}</h2><p>{primaryReason}</p><small><Clock3 size={13} />{primaryMeta}</small></div></div>
      {primaryTask ? <Button size="lg" type="button" onClick={() => void startPlannedItem(primaryTask)}>开始今日训练 <ArrowRight size={16} /></Button> : profile?.next_training && profileSourceSessionId ? <Button size="lg" type="button" disabled={startingRecommendation} onClick={() => void startProfileRecommendation()}>{startingRecommendation && <LoaderCircle className="spin" size={15} />}{startingRecommendation ? "正在准备来源证据" : "开始弱项复训"} <ArrowRight size={16} /></Button> : <Button asChild size="lg"><Link href={nextTrainingHref}>开始今日训练 <ArrowRight size={16} /></Link></Button>}
      {recommendationError && <p className={styles.coachError} role="alert">{recommendationError}</p>}
      <footer><span>推荐依据可核对，不会自动修改你的求职目标或训练记录。</span><Button asChild variant="link" size="sm"><Link href="/history?view=plan">查看本周计划 <ArrowRight size={13} /></Link></Button></footer>
    </section>}
    {remainingTasks.length > 0 && <section className={styles.todayPlan} aria-label="今日其他任务"><header><div><CheckCircle2 size={18} /><div><span>今日其他安排</span><strong>{remainingTasks.filter((item) => item.status !== "completed").length} 项待完成</strong></div></div></header><div>{remainingTasks.map((item) => <article key={item.id}><span className={item.status === "completed" ? styles.todayDone : ""}>{item.status === "completed" ? <CheckCircle2 size={15} /> : <Clock3 size={15} />}</span><div><strong>{item.title}</strong><small>{item.estimated_minutes} 分钟 · {item.completion_criteria}</small></div>{item.status !== "completed" && item.status !== "skipped" && <Button size="sm" type="button" onClick={() => void startPlannedItem(item)}>开始 <ArrowRight size={14} /></Button>}</article>)}</div></section>}
    <div className={styles.modeHeading}><h2>或者自主选择训练方式</h2><span>不会覆盖教练推荐</span></div>
    <section className={styles.modeGrid} aria-label="训练方式">
      {modes.map(({ href, title, description, icon: Icon }) => <Link className={styles.modeCard} href={href} key={title}>
        <span className={styles.modeIcon}><Icon size={19} /></span><div><h2>{title}</h2><p>{description}</p></div><span className={styles.modeAction}><ArrowRight size={16} /></span>
      </Link>)}
    </section>
    <section className={styles.recent}>
      <div className={styles.sectionHeading}><h2>继续上次训练</h2></div>
      {loading ? <div className={styles.empty}>正在读取训练记录</div> : recent.length ? <div className={styles.recentList}>{recent.map((item) => <Link className={styles.recentRow} href={`/training/${item.id}`} key={item.id}>
        <div><strong>{item.title}</strong><span>{COACHING_MODE_LABELS[item.mode]} · {item.target_role} · {item.turn_count} 轮</span></div><time>{new Date(item.updated_at).toLocaleDateString("zh-CN")}</time><Badge tone={item.status === "completed" ? "success" : item.status === "active" ? "accent" : "neutral"}>{item.status === "completed" ? "已完成" : item.status === "active" ? "进行中" : "待开始"}</Badge>
      </Link>)}</div> : <div className={styles.empty}><Sparkles size={18} />完成一次专项训练后，记录会出现在这里。</div>}
    </section>
  </main>;
}

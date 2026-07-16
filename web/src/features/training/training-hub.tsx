"use client";

import { ArrowRight, Bot, BriefcaseBusiness, CheckCircle2, Clock3, ListTree, MessageSquareText, Sparkles, Target } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { COACHING_MODE_LABELS, CoachingSummary, coachingSummarySchema } from "@/lib/coaching";
import { AbilityProfileData, abilityProfileSchema } from "@/lib/ability-profile";
import { type WeeklyPlanItem, weeklyPlanItemSchema } from "@/lib/career";
import { QUESTION_COACHING_SELECTION_KEY } from "@/lib/questions";

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
  const [plan, setPlan] = useState<AbilityProfileData["coaching"] | null>(null);
  const [today, setToday] = useState<WeeklyPlanItem[]>([]);

  useEffect(() => {
    let mounted = true;
    void fetch("/api/coaching-sessions", { cache: "no-store" }).then(async (response) => {
      if (!response.ok) return;
      const parsed = coachingSummarySchema.safeParse(await response.json());
      if (mounted && parsed.success) setRecent(parsed.data);
    }).finally(() => { if (mounted) setLoading(false); });
    void fetch("/api/profile", { cache: "no-store" }).then(async (response) => {
      if (!response.ok) return;
      const parsed = abilityProfileSchema.safeParse(await response.json());
      if (mounted && parsed.success) setPlan(parsed.data.coaching);
    });
    void fetch(`/api/career/today?date=${localDate()}`, { cache: "no-store" }).then(async (response) => {
      if (!response.ok) return;
      const parsed = weeklyPlanItemSchema.array().safeParse(await response.json());
      if (mounted && parsed.success) setToday(parsed.data);
    });
    return () => { mounted = false; };
  }, []);

  function startPlannedItem(item: WeeklyPlanItem) {
    if (item.task_type === "question_review" && item.question_id) {
      router.push(item.question_slug ? `/questions/${item.question_slug}` : "/questions");
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
    router.push(item.task_type === "mock_interview" ? "/setup" : item.task_type === "resume" ? "/profile" : "/history?view=plan");
  }

  return <main className={styles.page}>
    <header className={styles.intro}>
      <div><p className="eyebrow">训练中心</p><h1>今天重点练什么？</h1><p>选择一种训练方式，完成后再看证据与改进。</p></div>
    </header>
    {today.length > 0 && <section className={styles.todayPlan} aria-label="今日训练计划"><header><div><Bot size={18} /><div><span>AI 面试教练 · 今日计划</span><strong>{today.filter((item) => item.status !== "completed").length} 项待完成</strong></div></div><Link href="/history?view=plan">查看本周 <ArrowRight size={14} /></Link></header><div>{today.map((item) => <article key={item.id}><span className={item.status === "completed" ? styles.todayDone : ""}>{item.status === "completed" ? <CheckCircle2 size={15} /> : <Clock3 size={15} />}</span><div><strong>{item.title}</strong><small>{item.estimated_minutes} 分钟 · {item.completion_criteria}</small></div>{item.status !== "completed" && <button type="button" onClick={() => startPlannedItem(item)}>开始 <ArrowRight size={14} /></button>}</article>)}</div></section>}
    {plan?.next_mode && <section className={styles.dailyPlan}><div><Target size={18} /><div><span>下一次 10 分钟</span><strong>{plan.next_focus}</strong><small>连续训练 {plan.current_streak_days} 天 · 推荐 {plan.next_difficulty === "guided" ? "有骨架" : plan.next_difficulty === "assisted" ? "关键词提示" : "限时脱稿"}</small></div></div><Link href={`/training/new?mode=${plan.next_mode}&difficulty=${plan.next_difficulty}&focus=${encodeURIComponent(plan.next_focus ?? "")}`}>开始今日训练 <ArrowRight size={15} /></Link></section>}
    <section className={styles.modeGrid} aria-label="训练方式">
      {modes.map(({ href, title, description, icon: Icon }) => <Link className={styles.modeCard} href={href} key={title}>
        <span className={styles.modeIcon}><Icon size={21} /></span><h2>{title}</h2><p>{description}</p><span className={styles.modeAction}>开始训练 <ArrowRight size={16} /></span>
      </Link>)}
    </section>
    <section className={styles.recent}>
      <div className={styles.sectionHeading}><h2>继续上次训练</h2></div>
      {loading ? <div className={styles.empty}>正在读取训练记录</div> : recent.length ? <div className={styles.recentList}>{recent.map((item) => <Link className={styles.recentRow} href={`/training/${item.id}`} key={item.id}>
        <div><strong>{item.title}</strong><span>{COACHING_MODE_LABELS[item.mode]} · {item.target_role} · {item.turn_count} 轮</span></div><time>{new Date(item.updated_at).toLocaleDateString("zh-CN")}</time><span className={styles.status}>{item.status === "completed" ? "已完成" : item.status === "active" ? "进行中" : "待开始"}</span>
      </Link>)}</div> : <div className={styles.empty}><Sparkles size={18} />完成一次专项训练后，记录会出现在这里。</div>}
    </section>
  </main>;
}

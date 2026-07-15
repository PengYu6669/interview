"use client";

import { ArrowRight, BriefcaseBusiness, ListTree, MessageSquareText, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { COACHING_MODE_LABELS, CoachingSummary, coachingSummarySchema } from "@/lib/coaching";

import styles from "./training.module.css";

const modes = [
  { href: "/setup", title: "模拟面试", description: "完整面试流程与语音实战", icon: MessageSquareText },
  { href: "/training/new?mode=structured_expression", title: "结构化表达", description: "结论、职责、取舍与结果", icon: ListTree },
  { href: "/training/new?mode=business_sense", title: "业务 Sense", description: "目标、指标、优先级与验证", icon: BriefcaseBusiness },
];

export function TrainingHub() {
  const [recent, setRecent] = useState<CoachingSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    void fetch("/api/coaching-sessions", { cache: "no-store" }).then(async (response) => {
      if (!response.ok) return;
      const parsed = coachingSummarySchema.safeParse(await response.json());
      if (mounted && parsed.success) setRecent(parsed.data);
    }).finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  return <main className={styles.page}>
    <header className={styles.intro}>
      <div><p className="eyebrow">训练中心</p><h1>今天重点练什么？</h1><p>选择一种训练方式，完成后再看证据与改进。</p></div>
    </header>
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

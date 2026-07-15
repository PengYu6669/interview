"use client";

import {
  ArrowRight,
  BarChart3,
  BrainCircuit,
  CalendarDays,
  Clock3,
  FileChartColumn,
  History,
  LoaderCircle,
  Mic2,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { InterviewHistoryItem, interviewHistorySchema } from "@/lib/interview-report";
import { COACHING_MODE_LABELS, CoachingSummary, coachingSummarySchema } from "@/lib/coaching";
import { trainingContextLabels } from "@/lib/training-context";

type HistoryFilter = "all" | "interview" | "coaching" | "pending" | "reviewed";

const FILTERS: Array<{ value: HistoryFilter; label: string }> = [
  { value: "all", label: "全部" },
  { value: "interview", label: "模拟面试" },
  { value: "coaching", label: "专项训练" },
  { value: "pending", label: "待完成" },
  { value: "reviewed", label: "已复盘" },
];

function errorMessage(payload: unknown) {
  return typeof payload === "object" && payload && "detail" in payload
    ? String(payload.detail)
    : "训练记录读取失败";
}

function isFinished(item: InterviewHistoryItem) {
  return item.status === "completed" || item.status === "ended";
}

export function InterviewHistory() {
  const [items, setItems] = useState<InterviewHistoryItem[]>([]);
  const [coachingItems, setCoachingItems] = useState<CoachingSummary[]>([]);
  const [filter, setFilter] = useState<HistoryFilter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void Promise.all([
      fetch("/api/interview-sessions/history", { cache: "no-store" }),
      fetch("/api/coaching-sessions?limit=20", { cache: "no-store" }),
    ])
      .then(async ([interviewResponse, coachingResponse]) => {
        const interviewPayload: unknown = await interviewResponse.json();
        const coachingPayload: unknown = await coachingResponse.json();
        if (!interviewResponse.ok) throw new Error(errorMessage(interviewPayload));
        if (!coachingResponse.ok) throw new Error(errorMessage(coachingPayload));
        if (active) {
          setItems(interviewHistorySchema.parse(interviewPayload));
          setCoachingItems(coachingSummarySchema.parse(coachingPayload));
        }
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "训练记录读取失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const counts = useMemo(() => ({
    all: items.length + coachingItems.length,
    interview: items.length,
    coaching: coachingItems.length,
    pending: items.filter((item) => !isFinished(item) || (item.turn_count > 0 && item.report_status !== "ready")).length + coachingItems.filter((item) => item.status !== "completed").length,
    reviewed: items.filter((item) => item.report_status === "ready").length + coachingItems.filter((item) => item.status === "completed").length,
  }), [coachingItems, items]);

  const visibleItems = useMemo(() => items.filter((item) => {
    if (filter === "coaching") return false;
    if (filter === "pending") return !isFinished(item) || (item.turn_count > 0 && item.report_status !== "ready");
    if (filter === "reviewed") return item.report_status === "ready";
    return true;
  }), [filter, items]);
  const visibleCoaching = useMemo(() => coachingItems.filter((item) => {
    if (filter === "interview") return false;
    if (filter === "pending") return item.status !== "completed";
    if (filter === "reviewed") return item.status === "completed";
    return true;
  }), [coachingItems, filter]);

  if (loading) return <section className="review-empty-panel"><LoaderCircle className="spin" size={24} /><h2>正在读取训练记录</h2><p>正在从 PostgreSQL 汇总面试状态和回答证据。</p></section>;
  if (error) return <section className="review-empty-panel" role="alert"><History size={24} /><h2>训练记录读取失败</h2><p>{error}</p></section>;
  if (!items.length && !coachingItems.length) return <section className="review-empty-panel"><div className="review-empty-icon"><History size={24} /></div><h2>还没有训练记录</h2><p>完成模拟面试或专项训练后，回答与评价证据会出现在这里。</p><Link href="/training" className="primary-cta">开始第一次训练 <ArrowRight size={15} /></Link></section>;

  return <>
    <section className="history-summary-strip" aria-label="训练记录概览">
      <div><span>全部记录</span><strong>{counts.all}</strong></div>
      <div><span>模拟面试</span><strong>{counts.interview}</strong></div>
      <div><span>专项训练</span><strong>{counts.coaching}</strong></div>
      <div><span>已复盘</span><strong>{counts.reviewed}</strong></div>
    </section>
    <section className="history-filterbar">
      <div className="history-segments" aria-label="筛选训练记录">
        {FILTERS.map((item) => <button key={item.value} type="button" className={filter === item.value ? "active" : ""} aria-pressed={filter === item.value} onClick={() => setFilter(item.value)}>{item.label}<span>{counts[item.value]}</span></button>)}
      </div>
      <Link href="/profile"><BarChart3 size={14} />查看能力画像</Link>
    </section>
    {visibleItems.length > 0 && <section className="history-session-list" aria-label="模拟面试记录">{visibleItems.map((item) => <HistoryCard item={item} key={item.id} />)}</section>}
    {visibleCoaching.length > 0 && <section className="history-session-list coaching-history-list" aria-label="专项训练记录">{visibleCoaching.map((item) => <CoachingHistoryCard item={item} key={item.id} />)}</section>}
    {!visibleItems.length && !visibleCoaching.length && <section className="history-filter-empty"><History size={20} /><strong>这个分类下还没有记录</strong><span>切换其他分类，或开始一项新的训练。</span></section>}
  </>;
}

function CoachingHistoryCard({ item }: { item: CoachingSummary }) {
  const status = item.status === "completed" ? "已完成" : item.status === "active" ? "进行中" : "待开始";
  return <article className="history-session-card coaching-history-card">
    <div className="history-session-date"><BrainCircuit size={15} /><span>{new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.updated_at))}</span><b className={`history-status ${item.status}`}>{status}</b></div>
    <div className="history-session-main"><div><h2>{item.title}</h2><p>{COACHING_MODE_LABELS[item.mode]} · {item.target_role}</p></div><div className="history-session-metrics"><span><Mic2 size={14} />{item.turn_count} 轮回答</span><span>{item.channel === "voice" ? "语音训练" : "文字训练"}</span></div></div>
    <div className="history-session-action"><Link href={`/training/${item.id}`} className={item.status === "completed" ? "secondary-button" : "primary-cta"}>{item.status === "completed" ? "查看训练复盘" : "继续训练"} <ArrowRight size={15} /></Link></div>
  </article>;
}

function HistoryCard({ item }: { item: InterviewHistoryItem }) {
  const finished = isFinished(item);
  const status = item.status === "completed" ? "完整完成" : item.status === "ended" ? "中途结束" : item.status === "started" ? "进行中" : item.status === "paused" ? "已暂停" : "待开始";
  const date = item.completed_at ?? item.started_at;
  const context = trainingContextLabels(item);
  const progress = item.total_questions ? Math.round((item.answered_questions / item.total_questions) * 100) : 0;
  const reportAction = item.report_status === "ready"
    ? "查看复盘报告"
    : item.report_status === "generating"
      ? "查看生成进度"
      : item.report_status === "failed"
        ? "重新生成报告"
        : "生成复盘报告";

  return <article className="history-session-card">
    <div className="history-session-date"><CalendarDays size={15} /><span>{date ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(date)) : "尚未开始"}</span><b className={`history-status ${item.status}`}>{status}</b></div>
    <div className="history-session-main"><div><h2>{item.target_company ? `${item.target_company} · ` : ""}{item.target_role}</h2><p>{context.level} · {context.round} · {context.type}</p><small className="history-style">压力 {item.pressure_level} · 深度 {item.depth_level} · 引导 {item.guidance_level}</small></div><div className="history-session-metrics"><span><Clock3 size={14} />{item.duration_minutes} 分钟</span><span><Mic2 size={14} />{item.turn_count} 轮回答</span><span>{item.answered_questions} / {item.total_questions} 主问题</span></div></div>
    <div className="history-progress" aria-label={`主问题完成度 ${progress}%`}><i style={{ width: `${progress}%` }} /></div>
    <div className="history-session-action">{finished && item.turn_count > 0 ? <Link href={`/report?session=${item.id}`} className={`primary-cta report-action-${item.report_status}`}><FileChartColumn size={15} />{reportAction}</Link> : finished ? <Link href={`/interview?session=${item.id}`} className="secondary-button">查看结束状态 <ArrowRight size={15} /></Link> : item.status === "started" || item.status === "paused" ? <Link href={`/interview?session=${item.id}`} className="primary-cta">继续面试 <ArrowRight size={15} /></Link> : <Link href={`/interview?session=${item.id}`} className="secondary-button">进入等候室 <ArrowRight size={15} /></Link>}</div>
  </article>;
}

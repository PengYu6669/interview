"use client";

import { Bookmark, LoaderCircle, Save } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { userQuestionStateSchema, type UserQuestionState } from "@/lib/questions";

export function StudyActions({ questionId }: { questionId: string }) {
  const [state, setState] = useState<UserQuestionState>({ status: "unseen", bookmarked: false, note: "", review_interval_days: 0, review_streak: 0, last_reviewed_at: null, review_due_at: null });
  const [loggedIn, setLoggedIn] = useState<boolean | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    void fetch(`/api/questions/${questionId}/state`, { cache: "no-store" }).then(async (response) => { if (!active) return; setLoggedIn(response.ok); if (response.ok) setState(userQuestionStateSchema.parse(await response.json())); }).catch(() => { if (active) { setLoggedIn(true); setMessage("学习状态暂时无法读取"); } });
    return () => { active = false; };
  }, [questionId]);

  async function save() {
    setSaving(true);
    setMessage("");
    try {
      const response = await fetch(`/api/questions/${questionId}/state`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state) });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "保存失败，请稍后重试");
      setState(userQuestionStateSchema.parse(payload));
      setMessage("学习状态已保存");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  }

  if (loggedIn === null) return <section className="study-panel study-panel-loading"><LoaderCircle className="spin" size={18} /><span>正在读取学习状态</span></section>;
  if (loggedIn === false) return <section className="study-panel"><Bookmark size={20} /><h2>保存你的学习进度</h2><p>登录后可以收藏题目、记录掌握状态和个人笔记。</p><Link href="/login" className="primary-cta">登录后继续</Link></section>;
  return <section className="study-panel"><div className="panel-heading"><div><span>我的学习状态</span><small>只对当前账号可见</small></div><button type="button" className={`icon-action ${state.bookmarked ? "control-active" : ""}`} onClick={() => setState({ ...state, bookmarked: !state.bookmarked })} aria-label={state.bookmarked ? "取消收藏" : "收藏题目"}><Bookmark size={16} /></button></div><label className="field-label">掌握状态<select value={state.status} onChange={(event) => setState({ ...state, status: event.target.value })}><option value="unseen">未学习</option><option value="learning">学习中</option><option value="mastered">已掌握</option><option value="review">需要复习</option></select></label>{state.review_due_at && <p className="study-review-schedule">下次复习：{new Date(state.review_due_at).toLocaleDateString("zh-CN")} · 连续掌握 {state.review_streak} 次</p>}<label className="field-label">个人笔记<textarea value={state.note ?? ""} maxLength={10_000} onChange={(event) => setState({ ...state, note: event.target.value })} placeholder="记录你自己的理解、案例或仍然不清楚的地方" /></label>{message && <p className="study-message" role="status">{message}</p>}<button className="primary-cta full-width" type="button" disabled={saving} onClick={() => void save()}>{saving ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}{saving ? "正在保存" : "保存学习状态"}</button></section>;
}

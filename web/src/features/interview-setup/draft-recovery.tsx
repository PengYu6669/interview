"use client";

import { Clock3, FileText, LoaderCircle, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { TrainingDraft, TrainingDraftSummary, trainingDraftSchema, trainingDraftSummarySchema } from "@/lib/training-draft";

export function DraftRecovery({ onResume }: { onResume: (draft: TrainingDraft) => void }) {
  const [drafts, setDrafts] = useState<TrainingDraftSummary[]>([]);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void fetch("/api/drafts", { cache: "no-store" }).then(async (response) => {
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "训练草稿读取失败"));
      const parsed = trainingDraftSummarySchema.array().parse(payload);
      if (active) setDrafts(parsed);
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  async function resume(draftId: string) {
    setBusyId(draftId);
    setError("");
    try {
      const response = await fetch(`/api/drafts/${encodeURIComponent(draftId)}`, { cache: "no-store" });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "训练草稿读取失败"));
      onResume(trainingDraftSchema.parse(payload));
      setDrafts((current) => current.filter((draft) => draft.id !== draftId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "训练草稿读取失败");
    } finally {
      setBusyId("");
    }
  }

  async function remove(draftId: string) {
    setBusyId(draftId);
    setError("");
    try {
      const response = await fetch(`/api/drafts/${encodeURIComponent(draftId)}`, { method: "DELETE" });
      if (!response.ok && response.status !== 404) {
        const payload: unknown = await response.json();
        throw new Error(detail(payload, "训练草稿删除失败"));
      }
      setDrafts((current) => current.filter((draft) => draft.id !== draftId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "训练草稿删除失败");
    } finally {
      setBusyId("");
    }
  }

  if (!drafts.length && !error) return null;
  return <section className="draft-recovery" aria-labelledby="draft-recovery-title">
    <header><div><span>未完成的准备</span><h2 id="draft-recovery-title">继续 7 天内保存的训练草稿</h2></div><small>只保存提取文本，不保存上传原文件</small></header>
    {drafts.length > 0 && <div>{drafts.slice(0, 3).map((draft) => <article key={draft.id}>
      <FileText size={17} />
      <div><strong>{draft.target_role || "未命名岗位"}</strong><span>{draft.resume_filename}{draft.target_company ? ` · ${draft.target_company}` : ""}</span><small><Clock3 size={12} />{formatTime(draft.updated_at)} 更新 · {formatExpiry(draft.expires_at)}</small></div>
      <Button size="sm" variant="secondary" disabled={Boolean(busyId)} onClick={() => void resume(draft.id)}>{busyId === draft.id ? <LoaderCircle className="spin" size={14} /> : null}继续</Button>
      <Button size="icon" variant="ghost" disabled={Boolean(busyId)} aria-label={`删除 ${draft.target_role} 训练草稿`} onClick={() => void remove(draft.id)}><Trash2 size={15} /></Button>
    </article>)}</div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

function detail(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : fallback;
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function formatExpiry(value: string) {
  const days = Math.max(1, Math.ceil((new Date(value).getTime() - Date.now()) / 86_400_000));
  return `${days} 天后过期`;
}

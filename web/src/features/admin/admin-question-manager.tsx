"use client";

import { LoaderCircle, Plus, Search, ShieldCheck, Upload } from "lucide-react";
import Link from "next/link";
import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { adminQuestionListSchema, adminQuestionSchema, type AdminQuestion } from "@/lib/admin-questions";
import { aiJobStatusSchema, type AiJobStatus } from "@/lib/ai-jobs";

function responseDetail(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : fallback;
}

async function requestAdminQuestions() {
  const response = await fetch("/api/admin/questions", { cache: "no-store" });
  const payload: unknown = await response.json();
  if (!response.ok) throw new Error(responseDetail(payload, "候选题读取失败"));
  return adminQuestionListSchema.parse(payload);
}

export function AdminQuestionManager() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [questions, setQuestions] = useState<AdminQuestion[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | "draft" | "published">("draft");
  const [questionLimit, setQuestionLimit] = useState(30);
  const [job, setJob] = useState<AiJobStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [updatingId, setUpdatingId] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setQuestions(await requestAdminQuestions());
  }, []);

  useEffect(() => {
    let active = true;
    void Promise.all([
      requestAdminQuestions(),
      fetch("/api/jobs/latest?kind=question_import", { cache: "no-store" }).then(async (response) => response.ok ? aiJobStatusSchema.nullable().parse(await response.json()) : null),
    ]).then(([items, latestJob]) => { if (active) { setQuestions(items); if (latestJob) setJob(latestJob); } }).catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "题库管理加载失败"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [load]);

  useEffect(() => {
    if (!job || !["queued", "processing"].includes(job.status)) return;
    let active = true;
    const timer = window.setInterval(() => {
      void fetch(`/api/jobs/${job.id}`, { cache: "no-store" }).then(async (response) => {
        const payload: unknown = await response.json();
        if (!response.ok) throw new Error(responseDetail(payload, "任务状态读取失败"));
        const next = aiJobStatusSchema.parse(payload);
        if (!active) return;
        setJob(next);
        if (next.status === "completed" || next.status === "failed") {
          window.clearInterval(timer);
          setUploading(false);
          await load();
        }
      }).catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "任务状态读取失败"); });
    }, 2_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [job, load]);

  const visible = useMemo(() => questions.filter((question) => {
    const keyword = query.trim().toLowerCase();
    const matchesQuery = !keyword || `${question.title} ${question.prompt} ${question.source_document_name ?? ""}`.toLowerCase().includes(keyword);
    const matchesStatus = status === "all" || (status === "published" ? question.published : !question.published);
    return matchesQuery && matchesStatus;
  }), [query, questions, status]);

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const form = new FormData();
    form.set("file", file);
    form.set("question_limit", String(questionLimit));
    setUploading(true);
    setError("");
    try {
      const response = await fetch("/api/questions/import", { method: "POST", body: form });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(responseDetail(payload, "资料导入失败"));
      setJob(aiJobStatusSchema.parse(payload));
    } catch (reason) {
      setUploading(false);
      setError(reason instanceof Error ? reason.message : "资料导入失败");
    }
  }

  async function setPublication(question: AdminQuestion) {
    setUpdatingId(question.id);
    setError("");
    try {
      const response = await fetch(`/api/admin/questions/${question.id}/publication`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ published: !question.published }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(responseDetail(payload, "发布状态更新失败"));
      const saved = adminQuestionSchema.parse(payload);
      setQuestions((current) => current.map((item) => item.id === saved.id ? saved : item));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "发布状态更新失败");
    } finally {
      setUpdatingId("");
    }
  }

  const drafts = questions.filter((item) => !item.published).length;
  const published = questions.filter((item) => item.published).length;

  const busy = uploading || Boolean(job && ["queued", "processing"].includes(job.status));

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <SiteHeader active="admin" />
      <main className="mx-auto w-full max-w-[1180px] px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <span className="text-xs font-semibold text-[var(--muted)]">内容后台</span>
            <h1 className="mt-1 text-2xl font-semibold">公共题库管理</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button asChild variant="secondary"><Link href="/admin/questions/new"><Plus size={16} />新建题目</Link></Button>
            <select
              value={questionLimit}
              onChange={(event) => setQuestionLimit(Number(event.target.value))}
              className="h-10 rounded-md border border-[var(--line)] bg-white px-3 text-sm"
              aria-label="目标题数"
            >
              {[10, 20, 30, 50].map((value) => <option value={value} key={value}>{value} 题</option>)}
            </select>
            <Button type="button" onClick={() => inputRef.current?.click()} disabled={busy}>
              {busy ? <LoaderCircle className="spin" size={16} /> : <Upload size={16} />}
              上传资料
            </Button>
            <input ref={inputRef} hidden type="file" accept=".pdf,.docx,.md,.txt" onChange={importFile} />
          </div>
        </header>

        <section className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3" aria-label="题库统计">
          <Stat label="待审核" value={drafts} />
          <Stat label="已发布" value={published} />
          <div className="hidden sm:block"><Stat label="全部可管理" value={questions.length} /></div>
        </section>

        {job && ["queued", "processing"].includes(job.status) && (
          <section className="mt-4 flex items-center gap-3 rounded-md bg-[var(--bg-subtle)] px-4 py-3 text-sm" aria-live="polite">
            <LoaderCircle className="spin" size={16} />
            <span className="flex-1">{job.stage}</span>
            <strong>{job.progress}%</strong>
          </section>
        )}
        {job?.status === "failed" && <Alert>{job.error || "题目生成失败"}</Alert>}
        {error && <Alert>{error}</Alert>}

        <section className="mt-5 overflow-hidden rounded-md bg-white shadow-[var(--shadow-soft)]">
          <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex gap-1" role="tablist" aria-label="题目状态">
              {(["draft", "published", "all"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  role="tab"
                  aria-selected={status === value}
                  onClick={() => setStatus(value)}
                  className={`rounded-md px-3 py-2 text-sm ${status === value ? "bg-[var(--ink)] text-white" : "text-[var(--muted)] hover:bg-[var(--bg-subtle)]"}`}
                >
                  {value === "draft" ? "待审核" : value === "published" ? "已发布" : "全部"}
                </button>
              ))}
            </div>
            <label className="flex h-9 w-full items-center gap-2 rounded-md bg-[var(--bg-subtle)] px-3 sm:w-[260px]">
              <Search size={15} className="text-[var(--muted)]" />
              <span className="sr-only">搜索候选题</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索题目" className="min-w-0 flex-1 bg-transparent text-sm outline-none" />
            </label>
          </div>

          {loading && <div className="grid min-h-64 place-items-center text-[var(--muted)]"><LoaderCircle className="spin" size={18} /></div>}
          {!loading && visible.length === 0 && <div className="grid min-h-64 place-items-center text-sm text-[var(--muted)]">当前没有题目</div>}
          {!loading && visible.length > 0 && (
            <>
              <div className="divide-y divide-[var(--line)] md:hidden">
                {visible.map((question) => <QuestionCard key={question.id} question={question} updating={updatingId === question.id} onToggle={setPublication} />)}
              </div>
              <table className="hidden w-full border-collapse text-left md:table">
                <thead className="bg-[var(--bg-subtle)] text-xs text-[var(--muted)]">
                  <tr><th className="px-4 py-3 font-medium">题目</th><th className="px-4 py-3 font-medium">类型</th><th className="px-4 py-3 font-medium">状态</th><th className="px-4 py-3 text-right font-medium">操作</th></tr>
                </thead>
                <tbody>{visible.map((question) => <QuestionRow key={question.id} question={question} updating={updatingId === question.id} onToggle={setPublication} />)}</tbody>
              </table>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return <div className="rounded-md bg-white p-4 shadow-[var(--shadow-soft)]"><span className="text-xs text-[var(--muted)]">{label}</span><strong className="mt-1 block text-xl">{value}</strong></div>;
}

function Alert({ children }: { children: React.ReactNode }) {
  return <p className="mt-4 rounded-md bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger)]" role="alert">{children}</p>;
}

function Status({ published }: { published: boolean }) {
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs ${published ? "bg-[var(--bg-subtle)] text-[var(--ink)]" : "bg-[var(--soft)] text-[var(--muted)]"}`}>{published ? "已发布" : "待审核"}</span>;
}

type QuestionItemProps = {
  question: AdminQuestion;
  updating: boolean;
  onToggle: (question: AdminQuestion) => Promise<void>;
};

function Actions({ question, updating, onToggle }: QuestionItemProps) {
  return <div className="flex justify-end gap-2"><Button asChild variant="ghost" size="sm"><Link href={`/admin/questions/${question.id}`}>编辑</Link></Button><Button type="button" variant={question.published ? "secondary" : "primary"} size="sm" disabled={updating} onClick={() => void onToggle(question)}>{updating ? <LoaderCircle className="spin" size={14} /> : <ShieldCheck size={14} />}{question.published ? "下线" : "发布"}</Button></div>;
}

function QuestionCard(props: QuestionItemProps) {
  const { question } = props;
  return <article className="p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><strong className="block text-sm">{question.title}</strong><span className="mt-1 block text-xs text-[var(--muted)]">{question.difficulty} · {question.question_type}</span></div><Status published={question.published} /></div><div className="mt-4"><Actions {...props} /></div></article>;
}

function QuestionRow(props: QuestionItemProps) {
  const { question } = props;
  return <tr className="border-t border-[var(--line)]"><td className="max-w-md px-4 py-4"><strong className="block truncate text-sm">{question.title}</strong></td><td className="px-4 py-4 text-xs text-[var(--muted)]">{question.difficulty} · {question.question_type}</td><td className="px-4 py-4"><Status published={question.published} /></td><td className="px-4 py-4"><Actions {...props} /></td></tr>;
}

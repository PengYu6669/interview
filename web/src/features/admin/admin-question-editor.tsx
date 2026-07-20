"use client";

import { ArrowLeft, LoaderCircle, Save, ShieldCheck, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import { adminQuestionDetailSchema, adminQuestionSchema, type AdminQuestionDetail } from "@/lib/admin-questions";
import { cleanQuestionMarkdown } from "@/lib/question-markdown";

function detail(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : fallback;
}

function lines(value: string) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function emptyQuestion(): AdminQuestionDetail {
  return {
    id: "new", slug: "", title: "", prompt: "", difficulty: "进阶",
    question_type: "原理", topics: [], framework: "technical",
    source_document_id: null, source_document_name: null, source_document_version: null,
    published: false, owner_user_id: null, evidence_count: 0, created_at: "",
    intent: "", answer_outline: [], common_mistakes: [], content_markdown: "", evidence: [],
  };
}

export function AdminQuestionEditor({ questionId }: { questionId: string }) {
  const router = useRouter();
  const isNew = questionId === "new";
  const [question, setQuestion] = useState<AdminQuestionDetail | null>(() => isNew ? emptyQuestion() : null);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (isNew) {
      return;
    }
    let active = true;
    void fetch(`/api/admin/questions/${questionId}`, { cache: "no-store" })
      .then(async (response) => {
        const payload: unknown = await response.json();
        if (!response.ok) throw new Error(detail(payload, "题目读取失败"));
        if (active) setQuestion(adminQuestionDetailSchema.parse(payload));
      })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "题目读取失败"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [isNew, questionId]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question) return;
    const form = new FormData(event.currentTarget);
    setSaving(true);
    setError("");
    setMessage("");
    const payload = {
      title: String(form.get("title") ?? ""),
      prompt: String(form.get("prompt") ?? ""),
      difficulty: String(form.get("difficulty") ?? ""),
      question_type: String(form.get("question_type") ?? ""),
      framework: String(form.get("framework") ?? ""),
      intent: String(form.get("intent") ?? ""),
      answer_outline: lines(String(form.get("answer_outline") ?? "")),
      common_mistakes: lines(String(form.get("common_mistakes") ?? "")),
      topic_names: String(form.get("topic_names") ?? "").split(/[，,]/).map((item) => item.trim()).filter(Boolean),
      content_markdown: cleanQuestionMarkdown(String(form.get("content_markdown") ?? "")),
    };
    try {
      const response = await fetch(isNew ? "/api/admin/questions" : `/api/admin/questions/${questionId}`, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const responsePayload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(responsePayload, "保存失败"));
      const saved = adminQuestionDetailSchema.parse(responsePayload);
      setQuestion(saved);
      if (isNew) router.replace(`/admin/questions/${saved.id}`);
      setMessage("已保存");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (!question || isNew || !window.confirm("确定删除这道题吗？删除后不可恢复。")) return;
    setError("");
    const response = await fetch(`/api/admin/questions/${question.id}`, { method: "DELETE" });
    if (!response.ok) {
      const payload: unknown = await response.json();
      setError(detail(payload, "删除失败"));
      return;
    }
    router.replace("/admin/questions");
  }

  async function togglePublication() {
    if (!question) return;
    setPublishing(true);
    setError("");
    setMessage("");
    try {
      const response = await fetch(`/api/admin/questions/${questionId}/publication`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ published: !question.published }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "发布状态更新失败"));
      const saved = adminQuestionSchema.parse(payload);
      setQuestion({ ...question, ...saved });
      setMessage(saved.published ? "已发布" : "已下线");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "发布状态更新失败");
    } finally {
      setPublishing(false);
    }
  }

  return <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
    <SiteHeader active="admin" />
    <main className="mx-auto w-full max-w-[1040px] px-4 py-7 sm:px-6 lg:px-8">
      <Link href="/admin/questions" className="inline-flex items-center gap-2 text-sm text-[var(--muted)] hover:text-[var(--ink)]"><ArrowLeft size={16} />返回题库管理</Link>
      {loading && <div className="grid min-h-80 place-items-center text-[var(--muted)]"><LoaderCircle className="spin" size={22} /></div>}
      {!loading && (error && !question) && <p className="mt-6 rounded-md bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger)]" role="alert">{error}</p>}
      {question && <form onSubmit={save} className="mt-5 space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div><span className="text-xs font-semibold text-[var(--muted)]">公共题库</span><h1 className="mt-1 text-2xl font-semibold">{isNew ? "新建题目" : "编辑题目"}</h1></div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <span className="inline-flex h-9 items-center rounded-full bg-white px-3 text-xs shadow-[var(--shadow-soft)]">{question.published ? "已发布" : "待审核"}</span>
            {!isNew && <Button type="button" variant={question.published ? "secondary" : "primary"} onClick={() => void togglePublication()} disabled={publishing || saving}>{publishing ? <LoaderCircle className="spin" size={15} /> : <ShieldCheck size={15} />}{question.published ? "下线" : "发布"}</Button>}
            {!isNew && <Button type="button" variant="ghost" onClick={() => void remove()} disabled={publishing || saving}><Trash2 size={15} />删除</Button>}
          </div>
        </header>

        {(error || message) && <p className={`rounded-md px-4 py-3 text-sm ${error ? "bg-[var(--danger-bg)] text-[var(--danger)]" : "bg-white text-[var(--ink)] shadow-[var(--shadow-soft)]"}`} role={error ? "alert" : "status"}>{error || message}</p>}

        <section className="grid gap-4 rounded-md bg-white p-4 shadow-[var(--shadow-soft)] sm:p-6">
          <Field label="标题"><input name="title" defaultValue={question.title} maxLength={250} required /></Field>
          <Field label="题干"><textarea name="prompt" defaultValue={question.prompt} maxLength={8_000} rows={4} required /></Field>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="难度"><select name="difficulty" defaultValue={question.difficulty}><option>基础</option><option>进阶</option><option>高级</option></select></Field>
            <Field label="题型"><input name="question_type" defaultValue={question.question_type} maxLength={30} required /></Field>
            <Field label="回答框架"><input name="framework" defaultValue={question.framework} maxLength={30} required /></Field>
          </div>
          <Field label="知识点"><input name="topic_names" defaultValue={question.topics.map((topic) => topic.name).join("，")} maxLength={600} required /></Field>
          <Field label="考察意图"><textarea name="intent" defaultValue={question.intent} maxLength={4_000} rows={3} required /></Field>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="答案结构"><textarea name="answer_outline" defaultValue={question.answer_outline.join("\n")} rows={6} required /></Field>
            <Field label="常见错误"><textarea name="common_mistakes" defaultValue={question.common_mistakes.join("\n")} rows={6} required /></Field>
          </div>
          <Field label="Markdown 内容"><textarea name="content_markdown" defaultValue={question.content_markdown} maxLength={80_000} rows={14} className="font-mono" /></Field>
        </section>

        <div className="sticky bottom-4 flex justify-end"><Button type="submit" disabled={saving || publishing}>{saving ? <LoaderCircle className="spin" size={16} /> : <Save size={16} />}{isNew ? "创建题目" : "保存题目"}</Button></div>
      </form>}
    </main>
  </div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="grid gap-2 text-sm font-medium [&_input]:h-10 [&_input]:rounded-md [&_input]:bg-[var(--bg-subtle)] [&_input]:px-3 [&_input]:font-normal [&_input]:outline-none [&_input]:ring-[var(--ink)] focus-within:[&_input]:ring-1 [&_select]:h-10 [&_select]:rounded-md [&_select]:bg-[var(--bg-subtle)] [&_select]:px-3 [&_select]:font-normal [&_textarea]:rounded-md [&_textarea]:bg-[var(--bg-subtle)] [&_textarea]:px-3 [&_textarea]:py-2.5 [&_textarea]:font-normal [&_textarea]:leading-6 [&_textarea]:outline-none [&_textarea]:ring-[var(--ink)] focus-within:[&_textarea]:ring-1"><span>{label}</span>{children}</label>;
}

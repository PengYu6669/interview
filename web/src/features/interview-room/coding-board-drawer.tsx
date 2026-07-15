"use client";

import { CheckCircle2, CircleX, Code2, LoaderCircle, Play, Save, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import {
  codingRunSchema,
  codingWorkspaceSchema,
  type CodingRun,
  type CodingWorkspace,
} from "@/lib/interview-coding";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <div className="coding-editor-loading"><LoaderCircle className="spin" size={18} />正在加载编辑器</div>,
});

function responseError(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) return fallback;
  const detail = payload.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  return fallback;
}

export function CodingBoardDrawer({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const [workspace, setWorkspace] = useState<CodingWorkspace | null>(null);
  const [source, setSource] = useState("");
  const [complexityNotes, setComplexityNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [run, setRun] = useState<CodingRun | null>(null);

  useEffect(() => {
    let active = true;
    void fetch(`/api/interview-sessions/${encodeURIComponent(sessionId)}/coding`, { cache: "no-store" })
      .then(async (response) => ({ response, payload: await response.json().catch(() => null) }))
      .then(({ response, payload }) => {
        if (!active) return;
        if (!response.ok) throw new Error(responseError(payload, "Coding Board 暂时无法读取"));
        const parsed = codingWorkspaceSchema.safeParse(payload);
        if (!parsed.success) throw new Error("Coding Board 返回了无效数据");
        setWorkspace(parsed.data);
        setSource(parsed.data.snapshot?.source ?? parsed.data.problem.starter_code);
        setComplexityNotes(parsed.data.snapshot?.complexity_notes ?? "");
        setDirty(false);
      })
      .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Coding Board 暂时无法读取"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [sessionId]);

  async function persistWorkspace(): Promise<CodingWorkspace | null> {
    if (!workspace || !source.trim()) return null;
    setError("");
    try {
      const response = await fetch(`/api/interview-sessions/${encodeURIComponent(sessionId)}/coding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_snapshot_id: crypto.randomUUID(),
          base_revision: workspace.snapshot ? workspace.snapshot.revision + 1 : 0,
          source,
          complexity_notes: complexityNotes,
        }),
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(responseError(payload, "代码保存失败"));
      const parsed = codingWorkspaceSchema.safeParse(payload);
      if (!parsed.success) throw new Error("代码保存服务返回了无效数据");
      setWorkspace(parsed.data);
      setDirty(false);
      return parsed.data;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "代码保存失败");
      return null;
    }
  }

  async function saveWorkspace() {
    if (saving || running) return;
    setSaving(true);
    try {
      await persistWorkspace();
    } finally {
      setSaving(false);
    }
  }

  async function runCode() {
    if (!workspace || running || saving) return;
    setRunning(true);
    setError("");
    setRun(null);
    try {
      const current = dirty || !workspace.snapshot ? await persistWorkspace() : workspace;
      if (!current?.snapshot) return;
      const response = await fetch(`/api/interview-sessions/${encodeURIComponent(sessionId)}/coding/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_request_id: crypto.randomUUID(), snapshot_revision: current.snapshot.revision }),
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) throw new Error(responseError(payload, "代码运行失败"));
      const parsed = codingRunSchema.safeParse(payload);
      if (!parsed.success) throw new Error("代码运行服务返回了无效结果");
      setRun(parsed.data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "代码运行失败");
    } finally {
      setRunning(false);
    }
  }

  return <aside className="coding-board-drawer" aria-label="Coding Board">
    <header className="coding-drawer-header"><div><Code2 size={17} /><div><strong>Coding Board</strong><span>Python 3.12 · {workspace?.snapshot ? `版本 ${workspace.snapshot.revision + 1}` : "未保存"}</span></div></div><button type="button" onClick={onClose} aria-label="收起 Coding Board"><X size={18} /></button></header>
    {loading && <div className="coding-drawer-state"><LoaderCircle className="spin" size={20} />正在读取算法题</div>}
    {!loading && error && !workspace && <div className="coding-drawer-state error"><CircleX size={20} />{error}</div>}
    {workspace && <>
      <section className="coding-problem"><div><span>算法题</span><strong>{workspace.problem.title}</strong></div><p>{workspace.problem.description}</p>{workspace.problem.constraints.length > 0 && <ul>{workspace.problem.constraints.map((item) => <li key={item}>{item}</li>)}</ul>}<div className="coding-public-tests">{workspace.problem.public_tests.map((test) => <article key={test.name}><strong>{test.name}</strong><code>{JSON.stringify(test.arguments)} → {JSON.stringify(test.expected)}</code></article>)}</div></section>
      <section className="coding-editor-shell"><MonacoEditor height="100%" language="python" theme="vs-dark" value={source} onChange={(value) => { setSource(value ?? ""); setDirty(true); setRun(null); }} options={{ minimap: { enabled: false }, fontSize: 14, lineHeight: 22, scrollBeyondLastLine: false, automaticLayout: true, tabSize: 4, padding: { top: 12, bottom: 12 } }} /></section>
      <label className="complexity-field"><span>复杂度说明</span><textarea value={complexityNotes} onChange={(event) => { setComplexityNotes(event.target.value); setDirty(true); }} maxLength={2_000} placeholder="时间复杂度、空间复杂度与关键取舍" /></label>
      {error && <p className="coding-error" role="alert">{error}</p>}
      {run && <section className={`coding-run-result ${run.status}`}><header>{run.status === "passed" ? <CheckCircle2 size={16} /> : <CircleX size={16} />}<strong>{run.status === "passed" ? "公开测试全部通过" : run.status === "failed" ? "存在未通过测试" : "代码运行未完成"}</strong><span>{run.duration_ms} ms</span></header>{run.error && <p>{run.error}</p>}{run.tests.map((test) => <article key={test.name} className={test.passed ? "passed" : "failed"}><span>{test.passed ? "通过" : "失败"}</span><strong>{test.name}</strong>{test.error && <code>{test.error}</code>}</article>)}</section>}
      <footer className="coding-drawer-actions"><button type="button" className="secondary-action" disabled={!dirty || saving || running || !source.trim()} onClick={() => void saveWorkspace()}>{saving ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}{saving ? "正在保存" : "保存版本"}</button><button type="button" className="coding-run-button" disabled={saving || running || !source.trim()} onClick={() => void runCode()}>{running ? <LoaderCircle className="spin" size={15} /> : <Play size={15} />}{running ? "沙箱运行中" : "运行公开测试"}</button></footer>
    </>}
  </aside>;
}

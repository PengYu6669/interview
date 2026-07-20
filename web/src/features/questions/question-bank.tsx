"use client";

import { ArrowRight, BookOpen, Check, FileText, ListPlus, LoaderCircle, MessageSquareText, RefreshCw, Search, Sparkles, Trash2, Upload, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { aiJobStatusSchema, type AiJobStatus } from "@/lib/ai-jobs";
import { QUESTION_COACHING_SELECTION_KEY, QUESTION_INTERVIEW_SELECTION_KEY, questionDocumentSchema, questionSetDetailSchema, questionSetSummarySchema, questionSummarySchema, type QuestionDocumentSummary, type QuestionSetSummary, type QuestionSummary } from "@/lib/questions";

type Scope = "public" | "mine" | "review";

class QuestionRequestError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload && typeof payload.detail === "string" ? payload.detail : fallback;
}

async function requestQuestions(scope: Scope) {
  const endpoint = scope === "mine" ? "/api/questions/mine" : scope === "review" ? "/api/questions/review-due" : "/api/questions";
  const response = await fetch(endpoint, { cache: "no-store" });
  const payload: unknown = await response.json();
  if (!response.ok) throw new QuestionRequestError(errorMessage(payload, "题库读取失败"), response.status);
  return questionSummarySchema.array().parse(payload);
}

export function QuestionBank() {
  const router = useRouter();
  const [scope, setScope] = useState<Scope>("public");
  const [questions, setQuestions] = useState<QuestionSummary[]>([]);
  const [documents, setDocuments] = useState<QuestionDocumentSummary[]>([]);
  const [questionSets, setQuestionSets] = useState<QuestionSetSummary[]>([]);
  const [activeSet, setActiveSet] = useState<string>("");
  const [activeDocument, setActiveDocument] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [error, setError] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState("");
  const [importLoginRequired, setImportLoginRequired] = useState(false);
  const [importJob, setImportJob] = useState<AiJobStatus | null>(null);
  const [importElapsed, setImportElapsed] = useState(0);
  const [questionLimit, setQuestionLimit] = useState(30);
  const [loginRequired, setLoginRequired] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Map<string, { title: string; framework: string }>>(new Map());
  const [documentAction, setDocumentAction] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (nextScope: Scope = scope) => {
    setLoading(true);
    setError("");
    setLoginRequired(false);
    try {
      const [items, documentItems, setItems] = await Promise.all([
        requestQuestions(nextScope),
        nextScope === "mine" ? fetch("/api/questions/documents", { cache: "no-store" }).then(async (response) => {
          const payload: unknown = await response.json();
          if (!response.ok) throw new QuestionRequestError(errorMessage(payload, "题库资料读取失败"), response.status);
          return questionDocumentSchema.array().parse(payload);
        }) : Promise.resolve([]),
        nextScope === "mine" ? fetch("/api/questions/sets", { cache: "no-store" }).then(async (response) => questionSetSummarySchema.array().parse(await response.json())) : Promise.resolve([]),
      ]);
      setQuestions(items);
      setDocuments(documentItems);
      setQuestionSets(setItems);
    } catch (caught) {
      setQuestions([]);
      setError(caught instanceof Error ? caught.message : "题库读取失败");
      setLoginRequired(caught instanceof QuestionRequestError && caught.status === 401);
    } finally {
      setLoading(false);
    }
  }, [scope]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const [items, documentItems, setItems] = await Promise.all([
          requestQuestions(scope),
          scope === "mine" ? fetch("/api/questions/documents", { cache: "no-store" }).then(async (response) => {
            const payload: unknown = await response.json();
            if (!response.ok) throw new QuestionRequestError(errorMessage(payload, "题库资料读取失败"), response.status);
            return questionDocumentSchema.array().parse(payload);
          }) : Promise.resolve([]),
          scope === "mine" ? fetch("/api/questions/sets", { cache: "no-store" }).then(async (response) => questionSetSummarySchema.array().parse(await response.json())) : Promise.resolve([]),
        ]);
        if (active) { setQuestions(items); setDocuments(documentItems); setQuestionSets(setItems); setLoginRequired(false); }
      } catch (caught) {
        if (active) { setQuestions([]); setDocuments([]); setError(caught instanceof Error ? caught.message : "题库读取失败"); setLoginRequired(caught instanceof QuestionRequestError && caught.status === 401); }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [scope]);

  useEffect(() => {
    let active = true;
    void fetch("/api/jobs/latest?kind=question_import", { cache: "no-store" }).then(async (response) => {
      if (!response.ok) return;
      const payload: unknown = await response.json();
      if (!payload || !active) return;
      const job = aiJobStatusSchema.parse(payload);
      if (!["queued", "processing"].includes(job.status)) return;
      setImportJob(job);
      setImportElapsed(Math.max(0, Math.round((new Date().getTime() - new Date(job.created_at).getTime()) / 1000)));
      setImporting(job.status === "queued" || job.status === "processing");
    }).catch(() => undefined);
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!importJob || ["queued", "processing"].includes(importJob.status)) return;
    const delay = importJob.status === "completed" ? 5_000 : 10_000;
    const timer = window.setTimeout(() => {
      setImportJob((current) => current?.id === importJob.id ? null : current);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [importJob]);

  useEffect(() => {
    if (!importJob || !["queued", "processing"].includes(importJob.status)) return;
    let active = true;
    let refreshTick = 0;
    const poll = window.setInterval(() => {
      void fetch(`/api/jobs/${importJob.id}`, { cache: "no-store" }).then(async (response) => {
        const payload: unknown = await response.json();
        if (!response.ok) throw new QuestionRequestError(errorMessage(payload, "导入任务状态读取失败"), response.status);
        const job = aiJobStatusSchema.parse(payload);
        if (!active) return;
        setImportJob(job);
        setImportElapsed(Math.max(0, Math.round((new Date().getTime() - new Date(job.created_at).getTime()) / 1000)));
        if (job.status === "completed") {
          setImporting(false); setImportMessage("资料已完成解析、题目生成和索引，可以开始学习。"); setScope("mine"); await load("mine");
        } else if (job.status === "failed") {
          setImporting(false); setImportMessage(job.error ?? "资料导入失败");
          // Keep any partially generated questions already committed by the worker.
          setScope("mine");
          await load("mine");
        } else {
          // Incremental bank refresh: questions are committed per generation batch.
          refreshTick += 1;
          if (refreshTick % 2 === 0 || job.progress >= 55) {
            setScope("mine");
            await load("mine");
          }
        }
      }).catch((caught) => { if (active) setImportMessage(caught instanceof Error ? caught.message : "导入任务状态读取失败"); });
    }, 2_000);
    return () => { active = false; window.clearInterval(poll); };
  }, [importJob, load]);

  function selectScope(nextScope: Scope) {
    if (nextScope === scope) return;
    setLoading(true);
    setError("");
    setScope(nextScope);
    setActiveSet("");
  }

  async function openQuestionSet(questionSet: QuestionSetSummary) {
    setLoading(true); setError("");
    try {
      const response = await fetch(`/api/questions/sets/${questionSet.id}`, { cache: "no-store" });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "题目集读取失败"));
      const detail = questionSetDetailSchema.parse(payload);
      setQuestions(detail.questions); setActiveSet(questionSet.id); setActiveDocument(questionSet.document_id ?? "");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "题目集读取失败"); }
    finally { setLoading(false); }
  }

  const visible = useMemo(() => questions.filter((question) => {
    const keyword = query.trim().toLowerCase();
    const matchesText = !keyword || `${question.title} ${question.prompt} ${(question.topics ?? []).map((topic) => topic.name).join(" ")}`.toLowerCase().includes(keyword);
    const matchesDocument = scope !== "mine" || !activeDocument || question.source_document_id === activeDocument;
    return matchesText && matchesDocument && (!difficulty || question.difficulty === difficulty);
  }), [activeDocument, difficulty, query, questions, scope]);

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setImportLoginRequired(false);
    setImportMessage("正在上传资料…");
    const form = new FormData();
    form.set("file", file);
    form.set("question_limit", String(questionLimit));
    try {
      const response = await fetch("/api/questions/import", { method: "POST", body: form });
      const payload: unknown = await response.json();
      if (!response.ok) throw new QuestionRequestError(errorMessage(payload, "文档导入失败"), response.status);
      const job = aiJobStatusSchema.parse(payload);
      setImportJob(job); setImportElapsed(0); setImporting(true); setImportOpen(false);
      setImportMessage(`「${file.name}」已转入后台处理，可以离开当前页面。`);
    } catch (caught) {
      setImporting(false);
      setImportMessage(caught instanceof Error ? caught.message : "文档导入失败");
      setImportLoginRequired(caught instanceof QuestionRequestError && caught.status === 401);
    }
  }

  function toggleQuestion(question: QuestionSummary) {
    setSelected((current) => {
      const next = new Map(current);
      if (next.has(question.id)) next.delete(question.id);
      else if (next.size < 20) next.set(question.id, { title: question.title, framework: question.framework });
      return next;
    });
  }

  function startFromSelection() {
    const questions = Array.from(selected, ([id, item]) => ({ id, title: item.title }));
    sessionStorage.setItem(QUESTION_INTERVIEW_SELECTION_KEY, JSON.stringify({ questions }));
    router.push("/setup");
  }

  function selectAllVisible() {
    setSelected(new Map(visible.slice(0, 100).map((question) => [question.id, { title: question.title, framework: question.framework }])));
  }

  async function saveSelectionAsSet() {
    if (!selected.size) return;
    const name = window.prompt("题目集名称", "面试冲刺题目集")?.trim();
    if (!name) return;
    try {
      const response = await fetch("/api/questions/sets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, question_ids: Array.from(selected.keys()) }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "题目集创建失败"));
      setSelected(new Map()); setSelecting(false); await load("mine"); setScope("mine");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "题目集创建失败"); }
  }

  function startCoachingFromSelection() {
    if (selected.size !== 1) return;
    const [id, item] = selected.entries().next().value as [string, { title: string; framework: string }];
    sessionStorage.setItem(QUESTION_COACHING_SELECTION_KEY, JSON.stringify({ questions: [{ id, ...item }] }));
    router.push("/training/new?mode=structured_expression&source=question-bank");
  }

  async function runDocumentAction(document: QuestionDocumentSummary, action: "regenerate" | "delete") {
    if (action === "delete" && !window.confirm(`删除「${document.filename}」v${document.version} 及其全部题目？此操作不能撤销。`)) return;
    setDocumentAction(`${action}:${document.id}`);
    setError("");
    try {
      const response = await fetch(`/api/questions/documents/${document.id}${action === "regenerate" ? "/regenerate" : ""}`, { method: action === "regenerate" ? "POST" : "DELETE" });
      const payload: unknown = response.status === 204 ? null : await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, action === "delete" ? "资料删除失败" : "重新生成失败"));
      if (action === "regenerate") {
        const job = aiJobStatusSchema.parse(payload);
        setImportJob(job); setImportElapsed(0); setImporting(true);
        setImportMessage("正在从未覆盖知识点继续生成，可以离开当前页面。");
      }
      setActiveDocument("");
      if (action === "delete") await load("mine");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "资料操作失败");
    } finally {
      setDocumentAction("");
    }
  }

  return <main className="questions-page">
    <header className="questions-hero">
      <div><span className="section-kicker">学习题库</span><h1>从&ldquo;看过&rdquo;到&ldquo;能讲清楚&rdquo;</h1><p>按岗位和知识点练习经过审核的面试题。</p></div>
      {scope === "mine" && <button className="question-import-button" type="button" onClick={() => setImportOpen(true)}><Upload size={17} />导入私有资料</button>}
    </header>

    {importJob && <section className={`question-job-status ${importJob.status}`} aria-live="polite">
      <div className="question-job-copy">
        {importing ? <LoaderCircle className="spin" size={18} /> : importJob.status === "completed" ? <Check size={18} /> : <FileText size={18} />}
        <span><strong>{importJob.status === "failed" ? "资料处理失败" : importJob.status === "completed" ? "个人题库已更新" : importJob.stage}</strong><small>{importJob.status === "queued" || importJob.status === "processing" ? `已等待 ${importElapsed} 秒 · 题目边生成边出现` : importJob.error ?? importMessage}</small></span>
      </div>
      <b>{importJob.progress}%</b>
      <i><span style={{ width: `${importJob.progress}%` }} /></i>
      {importJob.status === "failed" && <button type="button" onClick={() => setImportOpen(true)}>重新导入</button>}
      {!importing && <button className="question-job-dismiss" type="button" aria-label="关闭资料处理状态" onClick={() => setImportJob(null)}><X size={15} /></button>}
    </section>}

    <section className="question-command-bar" aria-label="题库筛选">
      <div className="question-scope-tabs" role="tablist">
        <button className={scope === "public" ? "active" : ""} type="button" onClick={() => selectScope("public")} role="tab" aria-selected={scope === "public"}>公共题库</button>
        <button className={scope === "mine" ? "active" : ""} type="button" onClick={() => selectScope("mine")} role="tab" aria-selected={scope === "mine"}>我的题目</button>
        <button className={scope === "review" ? "active" : ""} type="button" onClick={() => selectScope("review")} role="tab" aria-selected={scope === "review"}>待复习</button>
      </div>
      <div className="flex items-center gap-2">
        <label className="question-search"><Search size={16} /><span className="sr-only">搜索题目</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索题目或知识点" /></label>
        <select className="min-h-9 rounded-lg border border-[var(--line)] bg-white px-2.5 text-xs text-[var(--ink)]" value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option value="">全部难度</option><option value="基础">基础</option><option value="进阶">进阶</option><option value="高级">高级</option></select>
      </div>
    </section>

    <div className="question-list-heading"><div><strong>{scope === "public" ? "精选学习题" : scope === "mine" ? activeSet ? "题目集内容" : "我的题目集" : "今天需要复习"}</strong><span>{loading ? "正在同步" : activeSet || scope !== "mine" ? `${visible.length} 道题目` : `${questionSets.length} 个题目集`}</span></div>{(scope !== "mine" || activeSet) && <div className="question-heading-actions">{selecting && activeSet && <button type="button" onClick={selectAllVisible}>全选当前集合</button>}<button className={selecting ? "active" : ""} type="button" onClick={() => { setSelecting((value) => !value); if (selecting) setSelected(new Map()); }}><ListPlus size={14} />{selecting ? "退出选择" : "选择题目"}</button></div>}</div>

    {scope === "mine" && !loading && questionSets.length > 0 && <section className="question-set-list" aria-label="我的题目集">
      {questionSets.map((questionSet) => { const document = documents.find((item) => item.id === questionSet.document_id); return <article className={activeSet === questionSet.id ? "active" : ""} key={questionSet.id}>
        <button type="button" onClick={() => void openQuestionSet(questionSet)}><FileText size={18} /><span><strong>{questionSet.name}</strong><small>{questionSet.question_count} 道题 · {questionSet.covered_knowledge_point_count}/{questionSet.knowledge_point_count} 个知识点</small><em>{questionSet.kind === "default" ? "资料生成" : "自定义"} · {questionSet.status === "ready" ? "可训练" : "生成中"}</em></span><ArrowRight size={16} /></button>
        {document && <div><button type="button" title="继续生成未覆盖知识点" aria-label={`继续生成 ${questionSet.name}`} disabled={Boolean(documentAction) || document.covered_knowledge_point_count >= document.knowledge_point_count} onClick={() => void runDocumentAction(document, "regenerate")}>{documentAction === `regenerate:${document.id}` ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />}</button><button type="button" title="删除资料及题目集" aria-label={`删除 ${questionSet.name}`} disabled={Boolean(documentAction)} onClick={() => void runDocumentAction(document, "delete")}><Trash2 size={14} /></button></div>}
      </article>; })}
    </section>}

    {scope === "mine" && !activeSet ? null : loading ? <div className="question-skeleton-list" aria-label="正在读取题库">{[1, 2, 3].map((item) => <div key={item}><i /><span /><span /></div>)}</div> : error ? <div className="question-state"><FileText size={24} /><strong>{loginRequired ? "登录后查看个人题库" : "暂时无法读取题库"}</strong><p>{error}</p>{loginRequired ? <Link className="primary-cta" href="/login?next=/questions">登录后继续</Link> : <button type="button" onClick={() => void load()}>重新加载</button>}</div> : visible.length ? <section className="question-card-list">{visible.map((question, index) => <article className={`question-select-row ${selected.has(question.id) ? "selected" : ""}`} key={question.id}>{selecting && <button className="question-select-toggle" type="button" onClick={() => toggleQuestion(question)} aria-label={selected.has(question.id) ? `取消选择 ${question.title}` : `选择 ${question.title}`}><span>{selected.has(question.id) && <Check size={13} />}</span></button>}<Link href={`/questions/${question.slug}`} className="question-row-card">
      <div className="question-card-number">{String(index + 1).padStart(2, "0")}</div>
      <div className="question-card-copy"><div className="question-card-meta"><span className={`difficulty difficulty-${question.difficulty}`}>{question.difficulty}</span><span>{question.question_type}</span>{scope === "mine" && <span className="owned-mark">可编辑</span>}</div><h2>{question.title}</h2><p>{question.prompt}</p><footer>{(question.topics ?? []).slice(0, 4).map((topic) => <span key={topic.id}>#{topic.name}</span>)}</footer></div>
      <div className="question-card-action"><BookOpen size={18} /><span>开始学习</span><ArrowRight size={16} /></div>
    </Link></article>)}</section> : <div className="question-state"><BookOpen size={24} /><strong>{scope === "mine" ? "还没有自己的题目" : "没有匹配的题目"}</strong><p>{scope === "mine" ? "导入 Word、PDF、Markdown 或文本资料，AI 会生成可编辑的学习题。" : "换一个关键词或难度试试。"}</p>{scope === "mine" && <button type="button" onClick={() => setImportOpen(true)}>导入第一份资料</button>}</div>}

    {selecting && <div className="question-selection-bar"><div><strong>已选 {selected.size} 道题</strong><span>{selected.size === 1 ? "可进行结构化重答" : selected.size ? "可保存题目集或发起模拟面试" : "请选择题目"}</span></div><button className="secondary-action" type="button" disabled={!selected.size} onClick={() => void saveSelectionAsSet()}><ListPlus size={15} />保存题目集</button><button className="secondary-action" type="button" disabled={selected.size !== 1} onClick={startCoachingFromSelection}><MessageSquareText size={15} />专项训练</button><button type="button" disabled={!selected.size || selected.size > 20} onClick={startFromSelection}>准备模拟面试 <ArrowRight size={15} /></button></div>}

    {importOpen && <div className="question-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setImportOpen(false); }}><section className="question-import-dialog" role="dialog" aria-modal="true" aria-labelledby="import-title"><button className="dialog-close" type="button" onClick={() => setImportOpen(false)} aria-label="关闭"><X size={18} /></button><div className="import-icon"><Sparkles size={22} /></div><h2 id="import-title">把资料变成学习题库</h2><p>系统会先识别知识点，再生成指定数量的题目。支持 PDF、Word（.docx）、Markdown 和 TXT，单个文件不超过 20MB。</p><label className="question-limit-control"><span><strong>目标题数</strong><em>{questionLimit} 题</em></span><input type="range" min="10" max="100" step="10" value={questionLimit} onChange={(event) => setQuestionLimit(Number(event.target.value))} /><small>默认 30 题；未达到目标题数时任务会明确失败。</small></label><button className="import-dropzone" type="button" disabled={importing} onClick={() => inputRef.current?.click()}>{importing ? <LoaderCircle className="spin" size={24} /> : <Upload size={24} />}<strong>{importing ? "正在上传资料" : "选择一个文件"}</strong><span>{importing ? "上传后会转入后台，可随时关闭弹窗" : "内容只用于生成你的个人题目"}</span></button><input ref={inputRef} hidden type="file" accept=".pdf,.docx,.md,.txt" onChange={importFile} />{importMessage && <div className={`import-feedback ${importing ? "working" : ""}`}>{importMessage}</div>}{importLoginRequired && <Link className="primary-cta full-width" href="/login?next=/questions">登录后导入资料</Link>}</section></div>}
  </main>;
}

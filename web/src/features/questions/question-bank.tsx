"use client";

import { ArrowRight, BookOpen, Check, FileText, ListPlus, LoaderCircle, Search, Sparkles, Upload, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

import { QUESTION_INTERVIEW_SELECTION_KEY, questionImportResultSchema, questionSummarySchema, type QuestionSummary } from "@/lib/questions";

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
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [error, setError] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState("");
  const [importLoginRequired, setImportLoginRequired] = useState(false);
  const [loginRequired, setLoginRequired] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Map<string, string>>(new Map());
  const inputRef = useRef<HTMLInputElement>(null);

  async function load(nextScope = scope) {
    setLoading(true);
    setError("");
    setLoginRequired(false);
    try {
      setQuestions(await requestQuestions(nextScope));
    } catch (caught) {
      setQuestions([]);
      setError(caught instanceof Error ? caught.message : "题库读取失败");
      setLoginRequired(caught instanceof QuestionRequestError && caught.status === 401);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    void requestQuestions(scope).then((items) => { if (active) { setQuestions(items); setLoginRequired(false); } }).catch((caught) => { if (active) { setQuestions([]); setError(caught instanceof Error ? caught.message : "题库读取失败"); setLoginRequired(caught instanceof QuestionRequestError && caught.status === 401); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [scope]);

  function selectScope(nextScope: Scope) {
    if (nextScope === scope) return;
    setLoading(true);
    setError("");
    setScope(nextScope);
  }

  const visible = useMemo(() => questions.filter((question) => {
    const keyword = query.trim().toLowerCase();
    const matchesText = !keyword || `${question.title} ${question.prompt} ${(question.topics ?? []).map((topic) => topic.name).join(" ")}`.toLowerCase().includes(keyword);
    return matchesText && (!difficulty || question.difficulty === difficulty);
  }), [difficulty, query, questions]);

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImporting(true);
    setImportLoginRequired(false);
    setImportMessage("正在解析文档、生成题目并建立检索索引，请不要关闭页面…");
    const form = new FormData();
    form.set("file", file);
    try {
      const response = await fetch("/api/questions/import", { method: "POST", body: form });
      const payload: unknown = await response.json();
      if (!response.ok) throw new QuestionRequestError(errorMessage(payload, "文档导入失败"), response.status);
      const result = questionImportResultSchema.parse(payload);
      setImportMessage(`已从「${file.name}」生成 ${result.questions.length} 道可编辑题目。`);
      setScope("mine");
      await load("mine");
    } catch (caught) {
      setImportMessage(caught instanceof Error ? caught.message : "文档导入失败");
      setImportLoginRequired(caught instanceof QuestionRequestError && caught.status === 401);
    } finally {
      setImporting(false);
    }
  }

  function toggleQuestion(question: QuestionSummary) {
    setSelected((current) => {
      const next = new Map(current);
      if (next.has(question.id)) next.delete(question.id);
      else if (next.size < 20) next.set(question.id, question.title);
      return next;
    });
  }

  function startFromSelection() {
    const questions = Array.from(selected, ([id, title]) => ({ id, title }));
    sessionStorage.setItem(QUESTION_INTERVIEW_SELECTION_KEY, JSON.stringify({ questions }));
    router.push("/setup");
  }

  return <main className="questions-page">
    <header className="questions-hero">
      <div><span className="section-kicker">学习题库</span><h1>从“看过”到“能讲清楚”</h1><p>系统学习公共题目，也可以把自己的 Word、PDF 和笔记变成可编辑题库。</p></div>
      <button className="question-import-button" type="button" onClick={() => setImportOpen(true)}><Upload size={17} />导入资料</button>
    </header>

    <section className="question-command-bar" aria-label="题库筛选">
      <div className="question-scope-tabs" role="tablist">
        <button className={scope === "public" ? "active" : ""} type="button" onClick={() => selectScope("public")} role="tab" aria-selected={scope === "public"}>公共题库</button>
        <button className={scope === "mine" ? "active" : ""} type="button" onClick={() => selectScope("mine")} role="tab" aria-selected={scope === "mine"}>我的题目</button>
        <button className={scope === "review" ? "active" : ""} type="button" onClick={() => selectScope("review")} role="tab" aria-selected={scope === "review"}>待复习</button>
      </div>
      <label className="question-search"><Search size={16} /><span className="sr-only">搜索题目</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索题目或知识点" /></label>
      <label className="question-difficulty"><span>难度</span><select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}><option value="">全部</option><option value="基础">基础</option><option value="进阶">进阶</option><option value="高级">高级</option></select></label>
    </section>

    <div className="question-list-heading"><div><strong>{scope === "public" ? "精选学习题" : scope === "mine" ? "我的资料题库" : "今天需要复习"}</strong><span>{loading ? "正在同步" : `${visible.length} 道题目`}</span></div><button className={selecting ? "active" : ""} type="button" onClick={() => { setSelecting((value) => !value); if (selecting) setSelected(new Map()); }}><ListPlus size={14} />{selecting ? "退出选择" : "选择题目发起面试"}</button></div>

    {loading ? <div className="question-skeleton-list" aria-label="正在读取题库">{[1, 2, 3].map((item) => <div key={item}><i /><span /><span /></div>)}</div> : error ? <div className="question-state"><FileText size={24} /><strong>{loginRequired ? "登录后查看个人题库" : "暂时无法读取题库"}</strong><p>{error}</p>{loginRequired ? <Link className="primary-cta" href="/login?next=/questions">登录后继续</Link> : <button type="button" onClick={() => void load()}>重新加载</button>}</div> : visible.length ? <section className="question-card-list">{visible.map((question, index) => <article className={`question-select-row ${selected.has(question.id) ? "selected" : ""}`} key={question.id}>{selecting && <button className="question-select-toggle" type="button" onClick={() => toggleQuestion(question)} aria-label={selected.has(question.id) ? `取消选择 ${question.title}` : `选择 ${question.title}`}><span>{selected.has(question.id) && <Check size={13} />}</span></button>}<Link href={`/questions/${question.slug}`} className="question-row-card">
      <div className="question-card-number">{String(index + 1).padStart(2, "0")}</div>
      <div className="question-card-copy"><div className="question-card-meta"><span className={`difficulty difficulty-${question.difficulty}`}>{question.difficulty}</span><span>{question.question_type}</span>{scope === "mine" && <span className="owned-mark">可编辑</span>}</div><h2>{question.title}</h2><p>{question.prompt}</p><footer>{(question.topics ?? []).slice(0, 4).map((topic) => <span key={topic.id}>#{topic.name}</span>)}</footer></div>
      <div className="question-card-action"><BookOpen size={18} /><span>开始学习</span><ArrowRight size={16} /></div>
    </Link></article>)}</section> : <div className="question-state"><BookOpen size={24} /><strong>{scope === "mine" ? "还没有自己的题目" : "没有匹配的题目"}</strong><p>{scope === "mine" ? "导入 Word、PDF、Markdown 或文本资料，AI 会生成可编辑的学习题。" : "换一个关键词或难度试试。"}</p>{scope === "mine" && <button type="button" onClick={() => setImportOpen(true)}>导入第一份资料</button>}</div>}

    {selecting && <div className="question-selection-bar"><div><strong>已选 {selected.size} 道题</strong><span>{selected.size ? "将结合简历和 JD 改写为面试重点" : "最多选择 20 道题"}</span></div><button type="button" disabled={!selected.size} onClick={startFromSelection}>准备这场面试 <ArrowRight size={15} /></button></div>}

    {importOpen && <div className="question-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !importing) setImportOpen(false); }}><section className="question-import-dialog" role="dialog" aria-modal="true" aria-labelledby="import-title"><button className="dialog-close" type="button" onClick={() => setImportOpen(false)} disabled={importing} aria-label="关闭"><X size={18} /></button><div className="import-icon"><Sparkles size={22} /></div><h2 id="import-title">把资料变成学习题库</h2><p>支持 PDF、Word（.docx）、Markdown 和 TXT，单个文件不超过 20MB。扫描版 PDF 会自动进入百度 OCR，并保留校对提醒。</p><button className="import-dropzone" type="button" disabled={importing} onClick={() => inputRef.current?.click()}>{importing ? <LoaderCircle className="spin" size={24} /> : <Upload size={24} />}<strong>{importing ? "正在处理资料" : "选择一个文件"}</strong><span>内容只用于生成你的个人题目</span></button><input ref={inputRef} hidden type="file" accept=".pdf,.docx,.md,.txt" onChange={importFile} />{importMessage && <div className={`import-feedback ${importing ? "working" : ""}`}>{importMessage}</div>}{importLoginRequired && <Link className="primary-cta full-width" href="/login?next=/questions">登录后导入资料</Link>}</section></div>}
  </main>;
}

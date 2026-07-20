"use client";

import { ArrowLeft, Bot, Check, Edit3, FileText, LoaderCircle, MessageSquareText, RefreshCw, Send, X } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { questionChatAnswerSchema, questionChatHistorySchema, questionDetailSchema, type QuestionChatMessageData, type QuestionDetail } from "@/lib/questions";
import { cleanQuestionMarkdown } from "@/lib/question-markdown";

import { StudyActions } from "./study-actions";

function errorMessage(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload && typeof payload.detail === "string" ? payload.detail : fallback;
}

function fallbackMarkdown(question: QuestionDetail) {
  const outline = (question.answer_outline ?? []).map((item, index) => `${index + 1}. ${item}`).join("\n");
  const mistakes = (question.common_mistakes ?? []).map((item) => `- ${item}`).join("\n");
  return `## 题目\n\n${question.prompt}\n\n## 考察意图\n\n${question.intent}\n\n## 回答框架\n\n${outline}\n\n## 常见误区\n\n${mistakes}`;
}

export function QuestionWorkspace({ slug, planId, planItemId }: { slug: string; planId?: string; planItemId?: string }) {
  const [question, setQuestion] = useState<QuestionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [markdown, setMarkdown] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatting, setChatting] = useState(false);
  const [chatError, setChatError] = useState("");
  const [chatAccess, setChatAccess] = useState<boolean | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<QuestionChatMessageData[]>([]);

  useEffect(() => {
    let active = true;
    void fetch(`/api/questions/${encodeURIComponent(slug)}`, { cache: "no-store" }).then(async (response) => {
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "题目读取失败"));
      if (!active) return;
      const detail = questionDetailSchema.parse(payload);
      setQuestion(detail);
      setTitle(detail.title);
      setMarkdown(cleanQuestionMarkdown(detail.content_markdown?.trim() || fallbackMarkdown(detail)));
      const historyResponse = await fetch(`/api/questions/${detail.id}/chat`, { cache: "no-store" });
      if (!active) return;
      if (historyResponse.status === 401) {
        setChatAccess(false);
      } else if (historyResponse.ok) {
        const historyPayload: unknown = await historyResponse.json();
        setChatAccess(true);
        if (historyPayload) {
          const history = questionChatHistorySchema.parse(historyPayload);
          setConversationId(history.conversation_id);
          setMessages(history.messages);
        }
      } else {
        setChatAccess(true);
        setChatError(errorMessage(await historyResponse.json(), "历史对话读取失败"));
      }
    }).catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "题目读取失败"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [slug]);

  async function saveContent() {
    if (!question) return;
    const cleanedMarkdown = cleanQuestionMarkdown(markdown);
    setSaving(true);
    setSaveMessage("");
    try {
      const response = await fetch(`/api/questions/${question.id}/content`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title, content_markdown: cleanedMarkdown }) });
      if (!response.ok) throw new Error(errorMessage(await response.json(), "保存失败"));
      setQuestion({ ...question, title, content_markdown: cleanedMarkdown });
      setMarkdown(cleanedMarkdown);
      setEditing(false);
      setSaveMessage("内容和检索索引已更新");
    } catch (caught) {
      setSaveMessage(caught instanceof Error ? caught.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    if (!question || !chatInput.trim()) return;
    setChatting(true);
    setChatError("");
    const userMessage = chatInput.trim();
    try {
      const response = await fetch(`/api/questions/${question.id}/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: userMessage, conversation_id: conversationId }) });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(errorMessage(payload, "AI 问答失败"));
      const nextAnswer = questionChatAnswerSchema.parse(payload);
      const now = new Date().toISOString();
      setConversationId(nextAnswer.conversation_id);
      setMessages((current) => [...current, { role: "user", content: userMessage, citations: [], created_at: now }, { role: "assistant", content: nextAnswer.answer_markdown, citations: nextAnswer.citations, created_at: now }]);
      setChatInput("");
    } catch (caught) {
      setChatError(caught instanceof Error ? caught.message : "AI 问答失败");
    } finally {
      setChatting(false);
    }
  }

  if (loading) return <main className="question-workspace-shell"><div className="question-detail-loading"><LoaderCircle className="spin" size={24} /><span>正在整理题目内容…</span></div></main>;
  if (error || !question) return <main className="question-workspace-shell"><Link className="back-link" href="/questions"><ArrowLeft size={15} />返回题库</Link><div className="question-state"><FileText size={24} /><strong>无法打开这道题</strong><p>{error}</p></div></main>;

  return <main className="question-workspace-shell">
    <div className="question-workspace-topbar"><Link className="back-link" href="/questions"><ArrowLeft size={15} />返回题库</Link><div>{question.editable && !editing && <button className="secondary-action" type="button" onClick={() => setEditing(true)}><Edit3 size={15} />编辑内容</button>}{editing && <><button className="ghost-action" type="button" onClick={() => { setEditing(false); setTitle(question.title); setMarkdown(question.content_markdown?.trim() || fallbackMarkdown(question)); }} disabled={saving}><X size={15} />取消</button><button className="primary-cta" type="button" onClick={() => void saveContent()} disabled={saving || !title.trim() || !markdown.trim()}>{saving ? <LoaderCircle className="spin" size={15} /> : <Check size={15} />}保存并更新索引</button></>}</div></div>
    <div className="question-workspace-layout">
      <article className="question-reading-pane">
        <header><div className="question-detail-meta"><span className={`difficulty difficulty-${question.difficulty}`}>{question.difficulty}</span><span>{question.question_type}</span>{question.topics?.map((topic) => <span key={topic.id}>{topic.name}</span>)}</div>{editing ? <input className="question-title-editor" value={title} maxLength={250} onChange={(event) => setTitle(event.target.value)} aria-label="题目标题" /> : <h1>{question.title}</h1>}{saveMessage && <div className="question-origin"><em>{saveMessage}</em></div>}</header>
        {editing ? <div className="markdown-editor"><div className="markdown-editor-label"><span>Markdown 内容</span><small>{markdown.length.toLocaleString()} / 80,000</small></div><textarea value={markdown} maxLength={80_000} onChange={(event) => setMarkdown(event.target.value)} spellCheck={false} /></div> : <div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown></div>}
      </article>

      <aside className="question-learning-rail">
        <section className="question-ai-panel"><div className="panel-heading"><div className="ai-avatar"><Bot size={17} /></div><div><h2>围绕题目问 AI</h2><p>连续对话，帮助你完善回答结构和表达</p></div>{messages.length > 0 && <button className="new-question-chat" type="button" disabled={chatting} onClick={() => { setMessages([]); setConversationId(null); setChatError(""); }} title="开始新对话"><RefreshCw size={14} /></button>}</div>{chatAccess === false ? <div className="question-chat-login"><MessageSquareText size={18} /><strong>登录后开始连续问答</strong><p>对话会保存到当前账号。</p><Link className="primary-cta" href={`/login?next=${encodeURIComponent(`/questions/${slug}`)}`}>登录后继续</Link></div> : <><div className="question-chat-messages" aria-live="polite">{messages.length ? messages.map((message, index) => <ChatMessage message={message} key={`${message.created_at}-${index}`} />) : <div className="question-chat-empty"><MessageSquareText size={18} /><span>继续追问实现细节、回答结构或容易遗漏的内容</span></div>}{chatting && <div className="question-chat-thinking"><LoaderCircle className="spin" size={15} />正在组织回答</div>}</div><form onSubmit={ask}><label><span className="sr-only">向 AI 提问</span><textarea value={chatInput} onChange={(event) => setChatInput(event.target.value)} maxLength={4_000} placeholder="继续追问这道题…" /></label><button type="submit" disabled={chatting || !chatInput.trim()}>{chatting ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />}发送</button></form>{chatError && <p className="chat-error" role="alert">{chatError}</p>}</>}</section>
        <StudyActions questionId={question.id} planId={planId} planItemId={planItemId} />
      </aside>
    </div>
  </main>;
}

function ChatMessage({ message }: { message: QuestionChatMessageData }) {
  if (message.role === "user") return <div className="question-chat-message user"><span>你</span><p>{message.content}</p></div>;
  return <div className="question-chat-message assistant"><span><Bot size={13} />AI 助教</span><div className="markdown-body compact"><ReactMarkdown remarkPlugins={[remarkGfm]}>{cleanQuestionMarkdown(message.content)}</ReactMarkdown></div></div>;
}

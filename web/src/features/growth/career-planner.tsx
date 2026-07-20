"use client";

import { Bot, CalendarDays, Check, History, LoaderCircle, Plus, Send, Target, TrendingUp, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { aiJobStatusSchema, type AiJobStatus } from "@/lib/ai-jobs";
import { useAuth } from "@/lib/auth-context";
import {
  careerProfileConversationResultSchema,
  careerWorkspaceSchema,
  weeklyPlanDraftSchema,
  weeklyPlanItemSchema,
  weeklyPlanSchema,
  type CareerWorkspace,
  type WeeklyPlan,
  type WeeklyPlanDraft,
  type WeeklyPlanItem,
} from "@/lib/career";

type ConversationMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
  showPlan?: boolean;
  quickActions?: string[];
};

type ConversationArchive = {
  id: string;
  title: string;
  updatedAt: string;
  messages: ConversationMessage[];
};

const dayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const slotLabels = { morning: "上午", afternoon: "下午", evening: "晚上", flexible: "灵活" } as const;
function historyStorageKey(userId: string) {
  return `career-planner-conversations-v1:${userId}`;
}

function localDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function mondayValue() {
  const date = new Date();
  const weekday = date.getDay() || 7;
  date.setDate(date.getDate() - weekday + 1);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(value: string, days: number) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + days);
  return localDate(date);
}

function detail(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : fallback;
}

async function readDraft(draftId: string, allowUnavailable = false) {
  const response = await fetch(`/api/career/weekly-plan/draft/${encodeURIComponent(draftId)}`, { cache: "no-store" });
  const payload: unknown = await response.json();
  if (allowUnavailable && (response.status === 404 || response.status === 422)) return null;
  if (!response.ok) throw new Error(detail(payload, "计划草稿读取失败"));
  return weeklyPlanDraftSchema.parse(payload);
}

export function CareerPlanner() {
  const { user } = useAuth();
  const [workspace, setWorkspace] = useState<CareerWorkspace | null>(null);
  const [plan, setPlan] = useState<WeeklyPlan | WeeklyPlanDraft | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [job, setJob] = useState<AiJobStatus | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [archives, setArchives] = useState<ConversationArchive[]>([]);
  const [conversationId, setConversationId] = useState(() => crypto.randomUUID());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const jobRef = useRef<AiJobStatus | null>(null);
  const generationInFlight = useRef(false);
  const userId = user?.id;

  useEffect(() => {
    jobRef.current = job;
  }, [job]);

  useEffect(() => {
    if (!userId) return;
    const activeUserId = userId;
    let active = true;
    async function initialize() {
      const [workspaceResponse, jobResponse] = await Promise.all([
        fetch("/api/career", { cache: "no-store" }),
        fetch("/api/jobs/latest?kind=career_plan", { cache: "no-store" }),
      ]);
      const payload: unknown = await workspaceResponse.json();
      if (!workspaceResponse.ok) throw new Error(detail(payload, "求职计划读取失败"));
      const parsed = careerWorkspaceSchema.parse(payload);
      if (!active) return;
      setWorkspace(parsed);
      setPlan(parsed.weekly_plan);
      const saved = readConversationArchives(activeUserId);
      setArchives(saved);
      const latest = saved[0];
      setMessages(latest?.messages.length ? latest.messages : [initialAssistantMessage(parsed)]);
      if (latest) setConversationId(latest.id);
      if (!jobResponse.ok) return;
      const jobPayload: unknown = await jobResponse.json();
      if (!jobPayload || !active) return;
      const latestJob = aiJobStatusSchema.parse(jobPayload);
      if (latestJob.status === "queued" || latestJob.status === "processing") {
        setJob(latestJob);
        setBusy(true);
      } else if (latestJob.status === "completed" && latestJob.resource_id) {
        const draft = await readDraft(latestJob.resource_id, true);
        if (!draft) return;
        if (!active) return;
        setPlan(draft);
        setDraftId(draft.id);
        setMessages([initialAssistantMessage(parsed), planReadyMessage()]);
      }
    }
    void initialize().catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "求职计划读取失败"); });
    return () => { active = false; };
  }, [userId]);

  useEffect(() => {
    const activeJob = jobRef.current;
    if (!activeJob || !["queued", "processing"].includes(activeJob.status)) return;
    const jobId = activeJob.id;
    let active = true;
    const timer = window.setInterval(() => {
      void fetch(`/api/jobs/${jobId}`, { cache: "no-store" }).then(async (response) => {
        const payload: unknown = await response.json();
        if (!response.ok) throw new Error(detail(payload, "排期状态读取失败"));
        const nextJob = aiJobStatusSchema.parse(payload);
        if (!active) return;
        setJob(nextJob);
        if (nextJob.status === "completed" && nextJob.resource_id) {
          window.clearInterval(timer);
          const draft = await readDraft(nextJob.resource_id);
          if (!draft) throw new Error("规划草稿已失效，请重新生成");
          if (!active) return;
          setPlan(draft);
          setDraftId(draft.id);
          setMessages((current) => [...current, planReadyMessage()]);
          setBusy(false);
          generationInFlight.current = false;
        } else if (nextJob.status === "failed") {
          window.clearInterval(timer);
          setError(nextJob.error ?? "本周计划生成失败");
          setBusy(false);
          generationInFlight.current = false;
        }
      }).catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "排期状态读取失败");
      });
    }, 2_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [job?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, busy]);

  useEffect(() => {
    if (!workspace || !userId || messages.length === 0) return;
    const firstUserMessage = messages.find((message) => message.role === "user")?.content;
    const archive: ConversationArchive = {
      id: conversationId,
      title: firstUserMessage?.slice(0, 28) || "新的求职计划",
      updatedAt: new Date().toISOString(),
      messages,
    };
    const storageKey = historyStorageKey(userId);
    const current = readConversationArchives(userId);
    const next = [archive, ...current.filter((item) => item.id !== conversationId)].slice(0, 12);
    window.localStorage.setItem(storageKey, JSON.stringify(next));
  }, [conversationId, messages, userId, workspace]);

  async function startGeneration(instruction: string) {
    if (generationInFlight.current) return;
    generationInFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/career/weekly-plan/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ week_start: mondayValue(), instruction }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "本周计划生成失败"));
      const createdJob = aiJobStatusSchema.parse(payload);
      setJob(createdJob);
      if (createdJob.status === "completed" && createdJob.resource_id) {
        const draft = await readDraft(createdJob.resource_id);
        if (!draft) throw new Error("规划草稿已失效，请重新生成");
        setPlan(draft);
        setDraftId(draft.id);
        setMessages((current) => [...current, planReadyMessage()]);
        setBusy(false);
        generationInFlight.current = false;
      } else if (createdJob.status === "failed") {
        throw new Error(createdJob.error ?? "本周计划生成失败");
      }
    } catch (reason) {
      generationInFlight.current = false;
      setBusy(false);
      setError(reason instanceof Error ? reason.message : "本周计划生成失败");
    }
  }

  async function sendMessage(text = input.trim()) {
    if (!text || busy || !workspace) return;
    setInput("");
    setError("");
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: "user", content: text }]);
    if (!workspace.profile.confirmed_at) {
      setBusy(true);
      try {
        const context = [...messages, { id: "current", role: "user" as const, content: text }]
          .slice(-8)
          .map((message) => `${message.role === "user" ? "用户" : "助手"}：${message.content}`)
          .join("\n")
          .slice(-1_000);
        const response = await fetch("/api/career/profile/from-message", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: context }),
        });
        const payload: unknown = await response.json();
        if (!response.ok) throw new Error(detail(payload, "求职画像生成失败"));
        const result = careerProfileConversationResultSchema.parse(payload);
        setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: result.reply }]);
        if (!result.profile) { setBusy(false); return; }
        setWorkspace((current) => current ? { ...current, profile: result.profile! } : current);
        setBusy(false);
        await startGeneration(text);
      } catch (reason) {
        setBusy(false);
        setError(reason instanceof Error ? reason.message : "求职画像生成失败");
      }
      return;
    }
    await startGeneration(text);
  }

  function startNewConversation() {
    if (!workspace) return;
    setConversationId(crypto.randomUUID());
    setMessages([initialAssistantMessage(workspace)]);
    setPlan(workspace.weekly_plan);
    setDraftId(null);
    setError("");
    setHistoryOpen(false);
  }

  function restoreConversation(archive: ConversationArchive) {
    setConversationId(archive.id);
    setMessages(archive.messages);
    setHistoryOpen(false);
  }

  async function savePlan() {
    if (!plan) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/career/weekly-plan", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ week_start: plan.week_start, goal: plan.goal, items: plan.items, status: "active", ...(draftId ? { draft_id: draftId } : {}) }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "周计划保存失败"));
      const saved = weeklyPlanSchema.parse(payload);
      setPlan(saved);
      setDraftId(null);
      setWorkspace((current) => current ? { ...current, weekly_plan: saved, plan_history: [saved, ...current.plan_history.filter((item) => item.id !== saved.id)] } : current);
      setMessages((current) => [...current, { id: crypto.randomUUID(), role: "assistant", content: "本周计划已确认。" }]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "周计划保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function toggleTask(item: WeeklyPlanItem) {
    const status = item.status === "completed" ? "pending" : "completed";
    if (draftId || !workspace?.weekly_plan || workspace.weekly_plan.id !== plan?.id) {
      setPlan((current) => current ? { ...current, items: current.items.map((entry) => entry.id === item.id ? weeklyPlanItemSchema.parse({ ...entry, status, completed_at: status === "completed" ? new Date().toISOString() : null }) : entry) } : current);
      return;
    }
    try {
      const response = await fetch(`/api/career/weekly-plan/${workspace.weekly_plan.id}/items/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "任务状态更新失败"));
      const saved = weeklyPlanItemSchema.parse(payload);
      setPlan((current) => current ? { ...current, items: current.items.map((entry) => entry.id === item.id ? saved : entry) } : current);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "任务状态更新失败");
    }
  }

  if (!workspace && !error) return <div className="flex min-h-[520px] items-center justify-center gap-2 text-sm text-[var(--muted)]"><LoaderCircle className="spin" size={18} />正在读取求职计划</div>;
  if (!workspace) return <p className="rounded-lg bg-[var(--danger-bg)] p-4 text-sm text-[var(--danger)]">{error}</p>;

  return (
    <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,3fr)_320px]">
      <section className="flex min-h-[650px] min-w-0 flex-col overflow-hidden rounded-lg bg-[var(--bg-surface)] shadow-[var(--shadow-soft)]">
        <header className="flex items-center justify-between gap-3 bg-[var(--bg-subtle)] px-5 py-4">
          <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-full bg-[var(--accent)] text-white"><Bot size={17} /></span>
          <div><h2 className="text-sm font-semibold">求职计划助手</h2><span className="text-xs text-[var(--muted)]">{plan ? formatWeek(plan.week_start) : "本周排期"}</span></div>
          </div>
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => { if (userId) setArchives(readConversationArchives(userId)); setHistoryOpen(true); }} className="grid size-9 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--ink)]" aria-label="查看对话历史" title="对话历史"><History size={17} /></button>
            <button type="button" onClick={startNewConversation} className="grid size-9 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--ink)]" aria-label="新建对话" title="新建对话"><Plus size={18} /></button>
          </div>
        </header>

        <div className="flex max-h-[620px] flex-1 flex-col gap-5 overflow-y-auto p-5 sm:p-7">
          {messages.map((message) => (
            <ConversationBubble key={message.id} message={message} plan={plan} draftId={draftId} busy={busy} onToggle={toggleTask} onSave={savePlan} onAction={sendMessage} />
          ))}
          {error && <p className="max-w-[82%] rounded-lg bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger)]" role="alert">{error}</p>}
          <div ref={messagesEndRef} />
        </div>

        <div className="flex items-end gap-2 bg-[var(--bg-subtle)] p-3 sm:p-4">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void sendMessage(); } }}
            placeholder={workspace.profile.confirmed_at ? "例如：周三晚上没时间，移到周四" : "例如：目标是前端工程师，每周 8 小时，周二、四、六训练"}
            rows={1}
            maxLength={1_000}
            className="min-h-11 flex-1 resize-none rounded-lg border border-[var(--border-default)] bg-white px-4 py-3 text-sm text-[var(--ink)] outline-none placeholder:text-[var(--text-placeholder)] focus:border-[var(--accent)]"
            aria-label="调整求职计划"
          />
          <Button size="icon" type="button" disabled={!input.trim() || busy} onClick={() => void sendMessage()} aria-label="发送"><Send size={17} /></Button>
        </div>
      </section>

      <ProgressOverview workspace={workspace} plan={plan} />
      {historyOpen && <ConversationHistory archives={archives} activeId={conversationId} onClose={() => setHistoryOpen(false)} onNew={startNewConversation} onSelect={restoreConversation} />}
    </div>
  );
}

function readConversationArchives(userId: string): ConversationArchive[] {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(historyStorageKey(userId)) || "[]");
    if (!Array.isArray(value)) return [];
    return value.filter((item): item is ConversationArchive => {
      return Boolean(item && typeof item === "object" && "id" in item && "messages" in item && Array.isArray(item.messages));
    });
  } catch {
    return [];
  }
}

function ConversationHistory({ archives, activeId, onClose, onNew, onSelect }: { archives: ConversationArchive[]; activeId: string; onClose: () => void; onNew: () => void; onSelect: (archive: ConversationArchive) => void }) {
  return <div className="fixed inset-0 z-50 flex justify-end bg-black/20" role="dialog" aria-label="对话历史">
    <div className="flex h-full w-full max-w-sm flex-col bg-[var(--bg-surface)] shadow-xl">
      <div className="flex items-center justify-between border-b border-[var(--border-default)] px-5 py-4"><strong className="text-sm">对话历史</strong><button type="button" onClick={onClose} className="grid size-8 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)]" aria-label="关闭"><X size={17} /></button></div>
      <div className="p-4"><Button type="button" variant="secondary" className="w-full justify-center gap-2" onClick={onNew}><Plus size={16} />新建对话</Button></div>
      <div className="flex-1 overflow-y-auto px-3 pb-4">
        {archives.length === 0 ? <p className="px-2 py-8 text-center text-sm text-[var(--muted)]">还没有对话记录</p> : archives.map((archive) => <button key={archive.id} type="button" onClick={() => onSelect(archive)} className={`mb-1 w-full rounded-md px-3 py-3 text-left hover:bg-[var(--bg-hover)] ${archive.id === activeId ? "bg-[var(--bg-subtle)]" : ""}`}><strong className="block truncate text-sm font-medium">{archive.title}</strong><span className="mt-1 block text-xs text-[var(--muted)]">{new Date(archive.updatedAt).toLocaleDateString("zh-CN")}</span></button>)}
      </div>
    </div>
  </div>;
}

function ConversationBubble({ message, plan, draftId, busy, onToggle, onSave, onAction }: {
  message: ConversationMessage;
  plan: WeeklyPlan | WeeklyPlanDraft | null;
  draftId: string | null;
  busy: boolean;
  onToggle: (item: WeeklyPlanItem) => Promise<void>;
  onSave: () => Promise<void>;
  onAction: (text: string) => Promise<void>;
}) {
  const assistant = message.role === "assistant";
  return (
    <div className={`flex max-w-[92%] gap-3 ${assistant ? "self-start" : "self-end flex-row-reverse"}`}>
      <span className={`grid size-8 shrink-0 place-items-center rounded-full text-xs font-semibold ${assistant ? "bg-[var(--bg-hover)] text-[var(--ink)]" : "bg-[var(--accent)] text-white"}`}>{assistant ? "AI" : "你"}</span>
      <div className="min-w-0">
        <p className={`rounded-lg px-4 py-3 text-sm leading-6 ${assistant ? "bg-[var(--bg-subtle)] text-[var(--ink)]" : "bg-[var(--accent)] text-white"}`}>{message.content}</p>
        {message.quickActions && <div className="mt-2 flex flex-wrap gap-2">{message.quickActions.map((action) => <button key={action} type="button" disabled={busy} onClick={() => void onAction(action)} className="rounded-full bg-[var(--bg-subtle)] px-3 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--ink)] disabled:opacity-50">{action}</button>)}</div>}
        {message.showPlan && plan && <ScheduleCard plan={plan} draftId={draftId} busy={busy} onToggle={onToggle} onSave={onSave} />}
      </div>
    </div>
  );
}

function ScheduleCard({ plan, draftId, busy, onToggle, onSave }: {
  plan: WeeklyPlan | WeeklyPlanDraft;
  draftId: string | null;
  busy: boolean;
  onToggle: (item: WeeklyPlanItem) => Promise<void>;
  onSave: () => Promise<void>;
}) {
  const days = useMemo(() => dayLabels.map((label, index) => {
    const date = addDays(plan.week_start, index);
    const items = plan.items.filter((item) => item.scheduled_date === date && item.status !== "skipped");
    return { label, date, items, minutes: items.reduce((total, item) => total + item.estimated_minutes, 0) };
  }), [plan]);
  return (
    <div className="mt-3 rounded-lg bg-white p-4 shadow-[var(--shadow-soft)] sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3"><strong className="text-sm">{plan.goal}</strong>{draftId && <Button size="sm" type="button" disabled={busy} onClick={() => void onSave()}>确认计划</Button>}</div>
      <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
        {days.map((day) => <div key={day.date} className={`grid min-w-[66px] place-items-center rounded-full px-3 py-2 text-center ${day.minutes ? "bg-[var(--accent)] text-white" : "bg-[var(--bg-subtle)] text-[var(--muted)]"}`}><span className="text-[11px]">{day.label}</span><strong className="text-xs">{day.minutes ? `${day.minutes} 分钟` : "休息"}</strong></div>)}
      </div>
      <div className="mt-4 grid gap-2">
        {plan.items.filter((item) => item.status !== "skipped").map((item) => (
          <button key={item.id} type="button" aria-pressed={item.status === "completed"} aria-label={`${item.status === "completed" ? "取消完成" : "标记完成"}：${item.title}`} onClick={() => void onToggle(item)} className="grid grid-cols-[20px_minmax(0,1fr)_auto] items-center gap-3 rounded-lg bg-[var(--bg-subtle)] px-3 py-3 text-left hover:bg-[var(--bg-hover)]">
            <span className={`grid size-[18px] place-items-center rounded-full ${item.status === "completed" ? "bg-[var(--accent)] text-white" : "bg-white ring-1 ring-[var(--border-hover)]"}`}>{item.status === "completed" && <Check size={11} strokeWidth={3} />}</span>
            <span className={`min-w-0 text-[13px] ${item.status === "completed" ? "text-[var(--muted)] line-through" : "text-[var(--ink)]"}`}><strong className="block truncate font-medium">{item.title}</strong><small className="mt-0.5 block text-xs text-[var(--muted)]">{dayLabel(item.scheduled_date, plan.week_start)} · {slotLabels[item.time_slot]}</small></span>
            <span className="text-xs text-[var(--muted)]">{item.estimated_minutes} 分钟</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ProgressOverview({ workspace, plan }: { workspace: CareerWorkspace; plan: WeeklyPlan | WeeklyPlanDraft | null }) {
  const tasks = plan?.items.filter((item) => item.status !== "skipped") ?? [];
  const completed = tasks.filter((item) => item.status === "completed").length;
  const progress = tasks.length ? Math.round(completed / tasks.length * 100) : 0;
  const recentGoal = [workspace.profile.target_role, workspace.profile.target_level].filter(Boolean).join(" · ") || "等待确认目标岗位";
  const companies = workspace.profile.target_companies.slice(0, 3).join("、");
  const weakness = plan?.basis.evidence_focus || "完成一次训练后更新";
  return (
    <aside className="h-fit rounded-lg bg-[var(--bg-surface)] p-5 shadow-[var(--shadow-soft)] xl:sticky xl:top-24">
      <h2 className="text-base font-semibold">求职进度</h2>
      <section className="mt-5 rounded-lg bg-[var(--bg-subtle)] p-4"><div className="flex items-center justify-between text-xs"><span className="text-[var(--muted)]">本周完成度</span><strong>{progress}%</strong></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white"><i className="block h-full rounded-full bg-[var(--accent)] transition-[width]" style={{ width: `${progress}%` }} /></div></section>
      <OverviewItem icon={Target} label="近期目标" value={recentGoal} meta={companies || `${workspace.profile.weekly_hours} 小时 / 周`} />
      <OverviewItem icon={CalendarDays} label="本周重点" value={plan?.goal || "等待本周计划"} meta={plan ? `${tasks.length} 项任务 · ${tasks.reduce((total, item) => total + item.estimated_minutes, 0)} 分钟` : undefined} />
      <OverviewItem icon={TrendingUp} label="能力短板" value={weakness} />
    </aside>
  );
}

function OverviewItem({ icon: Icon, label, value, meta }: { icon: typeof Target; label: string; value: string; meta?: string }) {
  return <section className="mt-4 rounded-lg bg-[var(--bg-subtle)] p-4"><div className="flex items-center gap-2 text-xs font-medium text-[var(--muted)]"><Icon size={14} />{label}</div><strong className="mt-2 block text-[13px] leading-5">{value}</strong>{meta && <small className="mt-1 block text-xs text-[var(--muted)]">{meta}</small>}</section>;
}

function initialAssistantMessage(workspace: CareerWorkspace): ConversationMessage {
  if (!workspace.profile.confirmed_at) return { id: crypto.randomUUID(), role: "assistant", content: "告诉我目标岗位、每周可投入时间和方便训练的日期。" };
  if (workspace.weekly_plan) return { id: crypto.randomUUID(), role: "assistant", content: "这是当前本周计划。需要调整时直接告诉我日期、时长或训练重点。", showPlan: true, quickActions: ["加强能力短板", "把训练集中到周末"] };
  return { id: crypto.randomUUID(), role: "assistant", content: `已读取 ${workspace.profile.target_role} 的求职画像和近期训练记录。`, quickActions: ["按建议生成本周计划"] };
}

function planReadyMessage(): ConversationMessage {
  return { id: crypto.randomUUID(), role: "assistant", content: "本周计划已更新。", showPlan: true };
}

function dayLabel(date: string, weekStart: string) {
  const index = Math.round((new Date(`${date}T12:00:00`).getTime() - new Date(`${weekStart}T12:00:00`).getTime()) / 86_400_000);
  return dayLabels[Math.max(0, Math.min(6, index))];
}

function formatWeek(weekStart: string) {
  const end = addDays(weekStart, 6);
  return `${weekStart.slice(5).replace("-", "/")} - ${end.slice(5).replace("-", "/")}`;
}

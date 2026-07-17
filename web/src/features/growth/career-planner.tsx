"use client";

import { Bot, Check, ChevronRight, CircleHelp, Clock3, LoaderCircle, Pencil, Plus, RefreshCw, Save, Target, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  careerProfileSchema,
  careerWorkspaceSchema,
  weeklyPlanDraftSchema,
  weeklyPlanItemSchema,
  weeklyPlanSchema,
  type CareerQuestionOption,
  type CareerWorkspace,
  type WeeklyPlan,
  type WeeklyPlanDraft,
  type WeeklyPlanItem,
} from "@/lib/career";
import { QUESTION_COACHING_SELECTION_KEY } from "@/lib/questions";
import { aiJobStatusSchema, remainingSeconds, type AiJobStatus } from "@/lib/ai-jobs";
import { AiWorkReceipt } from "@/components/ai-work-receipt";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

import styles from "./career-planner.module.css";

const dayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const slotLabels = { morning: "上午", afternoon: "下午", evening: "晚上", flexible: "灵活安排" } as const;
const taskLabels = {
  question_review: "题目学习",
  structured_expression: "结构化表达",
  business_sense: "业务 Sense",
  mock_interview: "模拟面试",
  resume: "简历优化",
  application: "投递跟进",
} as const;
const difficultyLabels = { guided: "有骨架", assisted: "关键词提示", pressure: "限时脱稿" } as const;

function mondayValue() {
  const date = new Date();
  const day = date.getDay() || 7;
  date.setDate(date.getDate() - day + 1);
  return localDate(date);
}

function localDate(date: Date) {
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

async function readCareerDraft(draftId: string) {
  const response = await fetch(`/api/career/weekly-plan/draft/${encodeURIComponent(draftId)}`, { cache: "no-store" });
  const payload: unknown = await response.json();
  if (response.status === 404 || response.status === 409) return null;
  if (!response.ok) throw new Error(detail(payload, "规划草稿读取失败"));
  return weeklyPlanDraftSchema.parse(payload);
}

function weeklyMixSummary(hours: number) {
  const questionSessions = hours <= 2 ? 1 : hours < 7 ? 2 : 3;
  const mockInterviews = hours < 3 ? 0 : hours < 7 ? 1 : 2;
  return `题目精练 ${questionSessions} 次（每次 2-3 道） · ${mockInterviews ? `模拟面试 ${mockInterviews} 场` : "限时追问 1 次"} · 结构化输出 1 次`;
}

type ProfileForm = {
  target_role: string;
  target_level: string;
  target_companies: string;
  preferred_cities: string;
  weekly_hours: number;
  available_weekdays: number[];
  preferred_time_slot: keyof typeof slotLabels;
  constraints: string;
};

export function CareerPlanner() {
  const router = useRouter();
  const [workspace, setWorkspace] = useState<CareerWorkspace | null>(null);
  const [profile, setProfile] = useState<ProfileForm>({
    target_role: "", target_level: "", target_companies: "", preferred_cities: "",
    weekly_hours: 5, available_weekdays: [0, 2, 4, 5], preferred_time_slot: "evening", constraints: "",
  });
  const [weekStart, setWeekStart] = useState(mondayValue());
  const [plan, setPlan] = useState<WeeklyPlan | WeeklyPlanDraft | null>(null);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState(0);
  const [profileExpanded, setProfileExpanded] = useState(false);
  const [busy, setBusy] = useState<"profile" | "plan" | "generate" | "">("");
  const [generationSeconds, setGenerationSeconds] = useState(0);
  const [generationJob, setGenerationJob] = useState<AiJobStatus | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const generationInFlight = useRef(false);

  useEffect(() => {
    let active = true;
    async function initialize() {
      const [workspaceResponse, jobResponse] = await Promise.all([
        fetch("/api/career", { cache: "no-store" }),
        fetch("/api/jobs/latest?kind=career_plan", { cache: "no-store" }),
      ]);
      const workspacePayload: unknown = await workspaceResponse.json();
      if (!workspaceResponse.ok) throw new Error(detail(workspacePayload, "求职计划读取失败"));
      const parsed = careerWorkspaceSchema.parse(workspacePayload);
      if (!active) return;
      setWorkspace(parsed);
      setProfileExpanded(!parsed.profile.confirmed_at);
      setProfile({
        target_role: parsed.profile.target_role,
        target_level: parsed.profile.target_level,
        target_companies: parsed.profile.target_companies.join("、"),
        preferred_cities: parsed.profile.preferred_cities.join("、"),
        weekly_hours: parsed.profile.weekly_hours,
        available_weekdays: parsed.profile.available_weekdays,
        preferred_time_slot: parsed.profile.preferred_time_slot,
        constraints: parsed.profile.constraints,
      });
      if (parsed.weekly_plan) {
        setPlan(parsed.weekly_plan);
        setWeekStart(parsed.weekly_plan.week_start);
        setSelectedDay(defaultPlanDay(parsed.weekly_plan.items, parsed.weekly_plan.week_start));
      }
      if (!jobResponse.ok) return;
      const jobPayload: unknown = await jobResponse.json();
      if (!jobPayload || !active) return;
      const job = aiJobStatusSchema.parse(jobPayload);
      setGenerationJob(job);
      if (job.status === "queued" || job.status === "processing") {
        setBusy("generate");
        return;
      }
      if (job.status === "completed" && job.resource_id) {
        const draft = await readCareerDraft(job.resource_id);
        if (!draft || !active) return;
        setPlan(draft);
        setDraftId(draft.id);
        setWeekStart(draft.week_start);
        setSelectedDay(defaultPlanDay(draft.items, draft.week_start));
        setMessage("已恢复尚未确认的 AI 训练草稿");
      }
    }
    void initialize().catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "求职计划读取失败"); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!generationJob || !["queued", "processing"].includes(generationJob.status)) return;
    let active = true;
    const poll = window.setInterval(() => {
      void fetch(`/api/jobs/${generationJob.id}`, { cache: "no-store" }).then(async (response) => {
        const payload: unknown = await response.json();
        if (!response.ok) throw new Error(detail(payload, "规划任务状态读取失败"));
        const job = aiJobStatusSchema.parse(payload);
        if (!active) return;
        setGenerationJob(job);
        if (job.status === "completed" && job.resource_id) {
          const draft = await readCareerDraft(job.resource_id);
          if (!draft) { setBusy(""); generationInFlight.current = false; return; }
          setPlan(draft); setDraftId(draft.id); setWeekStart(draft.week_start); setSelectedDay(defaultPlanDay(draft.items, draft.week_start));
          setMessage("AI 面试教练已生成草稿，检查后确认保存"); setBusy(""); generationInFlight.current = false;
        } else if (job.status === "failed") {
          setError(job.error ?? "AI 面试教练生成草稿失败"); setBusy(""); generationInFlight.current = false;
        }
      }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "规划任务状态读取失败"); });
    }, 2_000);
    return () => { active = false; window.clearInterval(poll); };
  }, [generationJob]);

  const generationCreatedAt = generationJob?.created_at;

  useEffect(() => {
    if (busy !== "generate") return;
    const startedAt = generationCreatedAt
      ? new Date(generationCreatedAt).getTime()
      : Date.now();
    const timer = window.setInterval(() => setGenerationSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1_000);
    return () => window.clearInterval(timer);
  }, [busy, generationCreatedAt]);

  const days = useMemo(() => dayLabels.map((label, index) => ({ label, date: addDays(weekStart, index) })), [weekStart]);
  const itemsByDay = useMemo(() => days.map((day) => (plan?.items ?? []).filter((item) => item.scheduled_date === day.date).sort((a, b) => a.position - b.position)), [days, plan]);
  const today = localDate(new Date());

  async function saveProfile(event: FormEvent) {
    event.preventDefault(); setBusy("profile"); setError(""); setMessage("");
    try {
      const response = await fetch("/api/career/profile", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...profile,
          target_companies: profile.target_companies.split(/[、,，]/).map((item) => item.trim()).filter(Boolean),
          preferred_cities: profile.preferred_cities.split(/[、,，]/).map((item) => item.trim()).filter(Boolean),
        }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "求职目标保存失败"));
      const saved = careerProfileSchema.parse(payload);
      setWorkspace((current) => current ? { ...current, profile: saved } : current);
      setProfileExpanded(false);
      setMessage("求职画像已确认，AI 面试教练可以据此规划训练");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "求职目标保存失败"); } finally { setBusy(""); }
  }

  async function generatePlan() {
    if (generationInFlight.current) return;
    generationInFlight.current = true;
    setGenerationSeconds(0);
    setBusy("generate"); setError(""); setMessage("");
    try {
      const response = await fetch("/api/career/weekly-plan/draft", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ week_start: weekStart }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "AI 训练日程生成失败"));
      const job = aiJobStatusSchema.parse(payload);
      setGenerationJob(job);
      setMessage("草稿已转入后台生成，可以离开当前页面");
    } catch (cause) { generationInFlight.current = false; setGenerationSeconds(0); setBusy(""); setError(cause instanceof Error ? cause.message : "AI 训练日程生成失败"); }
  }

  async function savePlan() {
    if (!plan) return;
    setBusy("plan"); setError(""); setMessage("");
    try {
      const response = await fetch("/api/career/weekly-plan", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ week_start: weekStart, goal: plan.goal, items: plan.items, status: "active", ...(draftId ? { draft_id: draftId } : {}) }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "训练日程保存失败"));
      const saved = weeklyPlanSchema.parse(payload);
      setPlan(saved); setDraftId(null);
      setWorkspace((current) => current ? { ...current, weekly_plan: saved, plan_history: [saved, ...current.plan_history.filter((item) => item.id !== saved.id)] } : current);
      setMessage("本周训练日程已确认");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "训练日程保存失败"); } finally { setBusy(""); }
  }

  function updateItem(id: string, patch: Partial<WeeklyPlanItem>) {
    setPlan((current) => current ? { ...current, items: current.items.map((item) => item.id === id ? weeklyPlanItemSchema.parse({ ...item, ...patch }) : item) } : current);
  }

  function replaceQuestion(item: WeeklyPlanItem, questionId: string) {
    const option = workspace?.question_options.find((entry) => entry.id === questionId);
    if (!option) return;
    const structured = item.task_type === "structured_expression" && ["star", "prep"].includes(option.framework);
    updateItem(item.id, {
      question_id: option.id,
      question_slug: option.slug,
      title: option.title,
      task_type: structured ? "structured_expression" : "question_review",
      coaching_mode: structured ? "structured_expression" : null,
      exercise_type: structured ? (option.framework === "star" ? "star_story" : "prep_pitch") : null,
      difficulty: structured ? (item.difficulty ?? "guided") : null,
    });
  }

  function addItem() {
    if (!plan) return;
    const option = workspace?.question_options.find((item) => !plan.items.some((entry) => entry.question_id === item.id));
    const item = weeklyPlanItemSchema.parse({
      id: crypto.randomUUID(), scheduled_date: days[selectedDay].date, time_slot: profile.preferred_time_slot,
      scheduled_time: null, estimated_minutes: 20, task_type: "question_review", title: option?.title ?? "自定义训练任务",
      reason: "由你手动加入本周日程", completion_criteria: "完成一次训练并记录结论", status: "pending", origin: "manual",
      question_id: option?.id ?? null, question_slug: option?.slug ?? null, coaching_mode: null, exercise_type: null, difficulty: null,
      position: plan.items.length, completed_at: null,
    });
    setPlan({ ...plan, items: [...plan.items, item] });
  }

  async function setItemStatus(item: WeeklyPlanItem, status: WeeklyPlanItem["status"]) {
    if (draftId || !workspace?.weekly_plan || workspace.weekly_plan.id !== plan?.id) {
      updateItem(item.id, { status, completed_at: status === "completed" ? new Date().toISOString() : null });
      return;
    }
    setError("");
    try {
      const response = await fetch(`/api/career/weekly-plan/${workspace.weekly_plan.id}/items/${item.id}`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "计划事项更新失败"));
      updateItem(item.id, weeklyPlanItemSchema.parse(payload));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "计划事项更新失败"); }
  }

  async function startItem(item: WeeklyPlanItem) {
    if (item.status !== "in_progress") await setItemStatus(item, "in_progress");
    if (item.task_type === "question_review" && item.question_id) {
      const option = workspace?.question_options.find((entry) => entry.id === item.question_id);
      if (option) router.push(`/questions/${option.slug}?plan=${workspace?.weekly_plan?.id ?? ""}&planItem=${item.id}`);
      return;
    }
    if (item.coaching_mode) {
      const option = workspace?.question_options.find((entry) => entry.id === item.question_id);
      if (option) sessionStorage.setItem(QUESTION_COACHING_SELECTION_KEY, JSON.stringify({ questions: [{ id: option.id, title: option.title, framework: option.framework }] }));
      const query = new URLSearchParams({ mode: item.coaching_mode, difficulty: item.difficulty ?? "guided", focus: item.completion_criteria, planItem: item.id });
      router.push(`/training/new?${query.toString()}`); return;
    }
    if (item.task_type === "mock_interview") router.push(`/setup?planItem=${item.id}`);
    else if (item.task_type === "resume") router.push("/history?view=plan");
    else if (item.task_type === "application") setMessage("投递任务已标记为进行中，完成跟进后可在卡片中标记完成");
  }

  async function deleteProfile() {
    if (!window.confirm("清除已确认的求职画像？已确认日程会保留。")) return;
    setBusy("profile"); setError("");
    try {
      const response = await fetch("/api/career/profile", { method: "DELETE" });
      if (!response.ok) throw new Error(detail(await response.json(), "求职画像清除失败"));
      const empty = careerProfileSchema.parse({ target_role: "", target_level: "", target_companies: [], preferred_cities: [], weekly_hours: 5, available_weekdays: [0, 2, 4, 5], preferred_time_slot: "evening", constraints: "", confirmed_at: null, updated_at: null });
      setWorkspace((current) => current ? { ...current, profile: empty } : current);
      setProfile({ target_role: "", target_level: "", target_companies: "", preferred_cities: "", weekly_hours: 5, available_weekdays: [0, 2, 4, 5], preferred_time_slot: "evening", constraints: "" });
      setProfileExpanded(true);
      setMessage("求职画像已清除");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "求职画像清除失败"); } finally { setBusy(""); }
  }

  async function deletePlan() {
    const saved = workspace?.weekly_plan;
    if (!saved || !window.confirm("删除当前周训练日程？此操作不能撤销。")) return;
    setBusy("plan"); setError("");
    try {
      const response = await fetch(`/api/career/weekly-plan/${saved.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error(detail(await response.json(), "训练日程删除失败"));
      setWorkspace((current) => current ? { ...current, weekly_plan: null, plan_history: current.plan_history.filter((item) => item.id !== saved.id) } : current);
      setPlan(null); setDraftId(null); setMessage("本周训练日程已删除");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "训练日程删除失败"); } finally { setBusy(""); }
  }

  if (!workspace && !error) return <section className={styles.loading}><LoaderCircle className="spin" size={22} />正在读取求职计划</section>;
  const confirmed = Boolean(workspace?.profile.confirmed_at);
  const planningBasisTip = plan ? [
    `${plan.basis.owned_question_count} 道个人题`,
    `${plan.basis.due_question_count} 道待复习`,
    `${plan.basis.recent_training_count} 次近期训练`,
    plan.basis.evidence_focus,
  ].filter(Boolean).join(" · ") : "";
  const generationLabel = generationJob?.stage ?? "正在创建后台任务";
  const generationRemaining = generationJob ? remainingSeconds(generationJob, generationSeconds) : 60;
  const trainingMixSummary = weeklyMixSummary(profile.weekly_hours);
  const generationStep = (generationJob?.progress ?? 0) < 35 ? 0 : (generationJob?.progress ?? 0) < 80 ? 1 : 2;

  return <div className={styles.layout}>
    {confirmed && !profileExpanded ? <section className={styles.profileSummary}><div><span>已确认画像</span><strong>{profile.target_role}{profile.target_level ? ` · ${profile.target_level}` : ""}</strong><small>每周 {profile.weekly_hours} 小时 · {profile.available_weekdays.length} 个训练日 · 偏好{slotLabels[profile.preferred_time_slot]}</small></div><button className={styles.secondaryButton} type="button" onClick={() => setProfileExpanded(true)}><Pencil size={14} />编辑画像</button></section> : <form className={styles.profilePanel} onSubmit={saveProfile}>
      <header className={styles.sectionHeader}><div><span>长期目标</span><h2>求职画像</h2></div>{confirmed && <small><Check size={13} />已确认</small>}</header>
      <p className={styles.privacy}>只有你确认的画像会参与规划，AI 建议不会自动修改长期数据。</p>
      <div className={styles.profileGrid}>
        <Field label="目标岗位"><input required maxLength={150} value={profile.target_role} onChange={(event) => setProfile({ ...profile, target_role: event.target.value })} /></Field>
        <Field label="目标级别"><input maxLength={50} value={profile.target_level} onChange={(event) => setProfile({ ...profile, target_level: event.target.value })} /></Field>
        <Field label="目标公司"><input value={profile.target_companies} onChange={(event) => setProfile({ ...profile, target_companies: event.target.value })} placeholder="用逗号分隔" /></Field>
        <Field label="意向城市"><input value={profile.preferred_cities} onChange={(event) => setProfile({ ...profile, preferred_cities: event.target.value })} placeholder="用逗号分隔" /></Field>
        <Field label="每周投入（小时）"><input type="number" min={1} max={80} value={profile.weekly_hours} onChange={(event) => setProfile({ ...profile, weekly_hours: Number(event.target.value) })} /></Field>
        <fieldset className={styles.slotField}><legend>偏好时段</legend><div>{Object.entries(slotLabels).map(([value, label]) => <button type="button" aria-pressed={profile.preferred_time_slot === value} onClick={() => setProfile({ ...profile, preferred_time_slot: value as keyof typeof slotLabels })} key={value}>{label}</button>)}</div></fieldset>
        <fieldset className={styles.weekdays}><legend>可训练星期</legend>{dayLabels.map((label, index) => <label key={label}><input type="checkbox" checked={profile.available_weekdays.includes(index)} onChange={() => setProfile({ ...profile, available_weekdays: profile.available_weekdays.includes(index) ? profile.available_weekdays.filter((item) => item !== index) : [...profile.available_weekdays, index].sort() })} /><span>{label.slice(1)}</span></label>)}</fieldset>
        <Field label="现实约束" wide><textarea maxLength={2000} value={profile.constraints} onChange={(event) => setProfile({ ...profile, constraints: event.target.value })} placeholder="例如：工作日晚间最多 1 小时、周日只做复盘" /></Field>
      </div>
      <div className={styles.actions}>{confirmed && <button className={styles.dangerButton} disabled={busy === "profile"} type="button" onClick={() => void deleteProfile()}><Trash2 size={14} />清除画像</button>}{confirmed && <button className={styles.secondaryButton} type="button" onClick={() => setProfileExpanded(false)}>取消编辑</button>}<Button disabled={busy === "profile" || profile.available_weekdays.length === 0} type="submit">{busy === "profile" ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}确认画像</Button></div>
    </form>}

    <section className={styles.scheduleSection}>
      <header className={styles.scheduleHeader}><div><span>本周行动</span><h2>训练日程</h2><p>{weekStart} 开始的一周</p></div><div>{workspace?.plan_history.length ? <label className={styles.historySelect}><span>历史周次</span><select value={draftId ? "draft" : plan?.id ?? ""} onChange={(event) => { const selected = workspace.plan_history.find((item) => item.id === event.target.value); if (selected) { setPlan(selected); setDraftId(null); setWeekStart(selected.week_start); setSelectedDay(defaultPlanDay(selected.items, selected.week_start)); } }}><option value="draft" disabled={!draftId}>{draftId ? "当前草稿" : "选择周次"}</option>{workspace.plan_history.map((item) => <option value={item.id} key={item.id}>{item.week_start} · {item.status === "completed" ? "已完成" : "进行中"}</option>)}</select></label> : null}<button className={styles.secondaryButton} type="button" disabled={!confirmed || busy === "generate"} onClick={() => void generatePlan()}>{busy === "generate" ? <LoaderCircle className="spin" size={15} /> : <RefreshCw size={15} />}{plan ? "重新生成草稿" : "生成本周草稿"}</button>{plan && <Button type="button" disabled={busy === "plan"} onClick={() => void savePlan()}><Save size={15} />{draftId ? "确认日程" : "保存调整"}</Button>}</div></header>
      {busy === "generate" && <div className={styles.generationPanel}><AiWorkReceipt title="正在生成本周训练草稿" description={generationLabel} activeStep={generationStep} steps={[{ label: "读取规划约束", detail: "岗位、可训练时间与现实限制" }, { label: "匹配训练证据", detail: "个人题库、待复习题与近期表现" }, { label: "生成可编辑草稿", detail: "确认前不会写入正式计划" }]} footer={`已等待 ${generationSeconds} 秒 · 预计还需约 ${generationRemaining} 秒，可以离开后再回来。`} /></div>}
      {!confirmed && <div className={styles.empty}><Target size={20} /><strong>先确认求职画像</strong><p>岗位、每周时间和可训练星期是生成可执行日程的必要约束。</p></div>}
      {confirmed && !plan && busy !== "generate" && <div className={styles.empty}><Bot size={22} /><strong>生成本周训练草稿</strong><p>会结合个人题库、待复习题和最近训练证据生成草稿，确认后才保存。</p><Button type="button" onClick={() => void generatePlan()}>生成本周草稿 <ChevronRight size={15} /></Button></div>}
      {plan && <>
        <div className={styles.planHint}><span><Bot size={14} />{trainingMixSummary}<button className={styles.helpButton} type="button" aria-label={`规划依据：${planningBasisTip}`} data-tip={planningBasisTip}><CircleHelp size={14} /></button></span>{draftId && <b>待确认</b>}</div>
        <label className={styles.weekGoal}><span>本周目标</span><input value={plan.goal} maxLength={500} onChange={(event) => setPlan({ ...plan, goal: event.target.value })} /></label>
        <nav className={styles.mobileDays} aria-label="选择日程日期">{days.map((day, index) => <button className={day.date === today ? styles.todayTab : undefined} type="button" aria-pressed={selectedDay === index} onClick={() => setSelectedDay(index)} key={day.date}><span>{day.label}</span><small>{day.date.slice(5)}</small><i>{itemsByDay[index].length}</i></button>)}</nav>
        <div className={styles.weekBoard}>{days.map((day, index) => <section className={`${styles.dayColumn} ${selectedDay === index ? styles.activeDay : ""} ${day.date === today ? styles.todayColumn : ""}`} key={day.date}><header><div><strong>{day.label}{day.date === today && <em>今天</em>}</strong><span>{day.date.slice(5)}</span></div><small>{itemsByDay[index].reduce((total, item) => total + item.estimated_minutes, 0)} 分钟</small></header><div className={styles.dayItems}>{itemsByDay[index].map((item) => <PlanTask item={item} questions={workspace?.question_options ?? []} onUpdate={updateItem} onReplaceQuestion={replaceQuestion} onMove={() => moveToNextDay(item, profile.available_weekdays, weekStart, updateItem)} onStatus={(status) => void setItemStatus(item, status)} onStart={() => void startItem(item)} key={item.id} />)}{itemsByDay[index].length === 0 && <div className={`${styles.restDay} ${index === 6 ? styles.sundayRest : ""}`}><span>{index === 6 ? "休息" : "暂无安排"}</span><small>{index === 6 ? "给这一周留一点余量" : "保持留白，按实际进度调整"}</small></div>}</div></section>)}</div>
        <div className={styles.scheduleFooter}><button className={styles.addButton} type="button" onClick={addItem}><Plus size={15} />添加到{days[selectedDay].label}</button>{workspace?.weekly_plan && !draftId && <button className={styles.dangerButton} type="button" disabled={busy === "plan"} onClick={() => void deletePlan()}><Trash2 size={14} />删除本周日程</button>}<small>AI 只生成草稿；日期、题目和难度都可以调整。</small></div>
      </>}
    </section>
    {message && <p className={styles.message}>{message}</p>}{error && <p className={styles.error} role="alert">{error}</p>}
  </div>;
}

function Field({ label, wide = false, children }: { label: string; wide?: boolean; children: React.ReactNode }) {
  return <label className={wide ? styles.wide : undefined}><span>{label}</span>{children}</label>;
}

function PlanTask({ item, questions, onUpdate, onReplaceQuestion, onMove, onStatus, onStart }: {
  item: WeeklyPlanItem; questions: CareerQuestionOption[]; onUpdate: (id: string, patch: Partial<WeeklyPlanItem>) => void;
  onReplaceQuestion: (item: WeeklyPlanItem, questionId: string) => void; onMove: () => void;
  onStatus: (status: WeeklyPlanItem["status"]) => void; onStart: () => void;
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  return <article className={`${styles.task} ${styles[`type_${item.task_type}`]} ${styles[item.status]}`}>
    <button className={styles.taskSummary} type="button" aria-label={`查看任务详情：${item.title}`} onClick={() => setDetailsOpen(true)}><span className={styles.taskKind}>{taskLabels[item.task_type]}</span><strong>{item.title}</strong><small><Clock3 size={11} />{item.scheduled_time?.slice(0, 5) ?? slotLabels[item.time_slot]} · {item.estimated_minutes} 分钟</small><span className={styles.taskState}>{item.status === "completed" ? <><Check size={12} />已完成</> : item.status === "in_progress" ? "进行中" : <ChevronRight size={14} />}</span></button>
    <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
      <DialogContent className="w-[min(620px,calc(100vw-32px))]">
        <DialogHeader>
          <span className="text-xs font-semibold text-[var(--accent-dark)]">{taskLabels[item.task_type]}</span>
          <DialogTitle className="mt-1">{item.title}</DialogTitle>
          <small className="mt-2 inline-flex items-center gap-1 text-xs text-[var(--muted)]"><Clock3 size={12} />{item.scheduled_time?.slice(0, 5) ?? slotLabels[item.time_slot]} · {item.estimated_minutes} 分钟{item.difficulty ? ` · ${difficultyLabels[item.difficulty]}` : ""}</small>
        </DialogHeader>
        <section className="mt-4 border-l-2 border-[var(--accent)] bg-[var(--surface-muted)] px-3 py-2"><span className="text-xs font-semibold">完成标准</span><p className="mt-1 text-xs leading-5 text-[var(--muted)]">{item.completion_criteria}</p></section>
        <section className="mt-2 border-l-2 border-[var(--line-strong)] bg-[var(--surface-muted)] px-3 py-2"><span className="text-xs font-semibold">推荐依据</span><p className="mt-1 text-xs leading-5 text-[var(--muted)]">{item.reason}</p></section>
        <div className={styles.detailPrimaryActions}><Button type="button" onClick={() => { setDetailsOpen(false); onStart(); }}>{item.status === "in_progress" ? "继续任务" : "开始任务"}<ChevronRight size={14} /></Button><Button variant="secondary" type="button" onClick={() => { onStatus(item.status === "completed" ? "pending" : "completed"); setDetailsOpen(false); }}><Check size={14} />{item.status === "completed" ? "取消完成" : "标记完成"}</Button></div>
        <div className={styles.taskControls}><label className={styles.questionSelect}>任务名称<input maxLength={200} value={item.title} onChange={(event) => onUpdate(item.id, { title: event.target.value })} /></label><label>日期<input type="date" value={item.scheduled_date} onChange={(event) => onUpdate(item.id, { scheduled_date: event.target.value })} /></label><label>时段<select value={item.time_slot} onChange={(event) => onUpdate(item.id, { time_slot: event.target.value as WeeklyPlanItem["time_slot"] })}>{Object.entries(slotLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>具体时间<input type="time" value={item.scheduled_time?.slice(0, 5) ?? ""} onChange={(event) => onUpdate(item.id, { scheduled_time: event.target.value || null })} /></label><label>分钟<input type="number" min={5} max={240} value={item.estimated_minutes} onChange={(event) => onUpdate(item.id, { estimated_minutes: Number(event.target.value) })} /></label>{item.difficulty && <label>难度<select value={item.difficulty} onChange={(event) => onUpdate(item.id, { difficulty: event.target.value as WeeklyPlanItem["difficulty"] })}>{Object.entries(difficultyLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>}{item.question_id && <label className={styles.questionSelect}>换一道题<select value={item.question_id} onChange={(event) => onReplaceQuestion(item, event.target.value)}>{questions.filter((question) => question.id === item.question_id || !question.review_due || question.owned).map((question) => <option value={question.id} key={question.id}>{question.title}</option>)}</select></label>}<label className={styles.questionSelect}>完成标准<textarea maxLength={500} value={item.completion_criteria} onChange={(event) => onUpdate(item.id, { completion_criteria: event.target.value })} /></label></div>
        <DialogFooter><Button variant="secondary" type="button" onClick={onMove}>移到下一个可训练日</Button><Button variant="danger" type="button" onClick={() => { onStatus("skipped"); setDetailsOpen(false); }}><Trash2 size={14} />跳过任务</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </article>;
}

function firstScheduledDay(items: WeeklyPlanItem[], weekStart: string) {
  if (!items.length) return 0;
  return Math.max(0, Math.min(6, Math.round((new Date(`${items[0].scheduled_date}T12:00:00`).getTime() - new Date(`${weekStart}T12:00:00`).getTime()) / 86_400_000)));
}

function defaultPlanDay(items: WeeklyPlanItem[], weekStart: string) {
  const today = localDate(new Date());
  const todayItems = items.filter((item) => item.scheduled_date === today);
  return firstScheduledDay(todayItems.length ? todayItems : items, weekStart);
}

function moveToNextDay(item: WeeklyPlanItem, available: number[], weekStart: string, update: (id: string, patch: Partial<WeeklyPlanItem>) => void) {
  const current = firstScheduledDay([item], weekStart);
  const next = available.find((day) => day > current) ?? available[0];
  update(item.id, { scheduled_date: addDays(weekStart, next) });
}

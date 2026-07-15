"use client";

import { Check, LoaderCircle, Plus, Save, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { careerWorkspaceSchema, type CareerWorkspace, type WeeklyPlanItem } from "@/lib/career";

const categoryLabels: Record<WeeklyPlanItem["category"], string> = {
  learning: "学习训练",
  interview: "模拟面试",
  resume: "简历优化",
  application: "投递跟进",
};

function mondayValue() {
  const date = new Date();
  const day = date.getDay() || 7;
  date.setDate(date.getDate() - day + 1);
  return date.toISOString().slice(0, 10);
}

function detail(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : fallback;
}

export function CareerPlanner() {
  const [workspace, setWorkspace] = useState<CareerWorkspace | null>(null);
  const [profile, setProfile] = useState({ target_role: "", target_level: "", target_companies: "", preferred_cities: "", weekly_hours: 5, constraints: "" });
  const [weekStart, setWeekStart] = useState(mondayValue());
  const [goal, setGoal] = useState("");
  const [items, setItems] = useState<WeeklyPlanItem[]>([]);
  const [saving, setSaving] = useState<"profile" | "plan" | "">("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void fetch("/api/career", { cache: "no-store" }).then(async (response) => {
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "求职计划读取失败"));
      const parsed = careerWorkspaceSchema.parse(payload);
      if (!active) return;
      setWorkspace(parsed);
      setProfile({
        target_role: parsed.profile.target_role ?? "",
        target_level: parsed.profile.target_level ?? "",
        target_companies: (parsed.profile.target_companies ?? []).join("、"),
        preferred_cities: (parsed.profile.preferred_cities ?? []).join("、"),
        weekly_hours: parsed.profile.weekly_hours ?? 5,
        constraints: parsed.profile.constraints ?? "",
      });
      if (parsed.weekly_plan) {
        setWeekStart(parsed.weekly_plan.week_start);
        setGoal(parsed.weekly_plan.goal);
        setItems(parsed.weekly_plan.items);
      } else if (parsed.suggested_focus) {
        setGoal(parsed.suggested_focus);
      }
    }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "求职计划读取失败"); });
    return () => { active = false; };
  }, []);

  async function saveProfile(event: FormEvent) {
    event.preventDefault(); setSaving("profile"); setError(""); setMessage("");
    try {
      const response = await fetch("/api/career/profile", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...profile, target_companies: profile.target_companies.split(/[、,，]/).map((item) => item.trim()).filter(Boolean), preferred_cities: profile.preferred_cities.split(/[、,，]/).map((item) => item.trim()).filter(Boolean) }) });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "求职目标保存失败"));
      setMessage("求职目标已由你确认并保存");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "求职目标保存失败"); } finally { setSaving(""); }
  }

  async function savePlan(event: FormEvent) {
    event.preventDefault(); setSaving("plan"); setError(""); setMessage("");
    try {
      const response = await fetch("/api/career/weekly-plan", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ week_start: weekStart, goal, items, status: items.length > 0 && items.every((item) => item.completed_count === item.target_count) ? "completed" : "active" }) });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(detail(payload, "周计划保存失败"));
      setMessage("本周计划已保存，可随进度继续调整");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "周计划保存失败"); } finally { setSaving(""); }
  }

  function addItem() {
    setItems((current) => [...current, { id: crypto.randomUUID(), category: "learning", title: "", target_count: 1, completed_count: 0 }]);
  }

  function updateItem(id: string, patch: Partial<WeeklyPlanItem>) {
    setItems((current) => current.map((item) => item.id === id ? { ...item, ...patch } : item));
  }

  if (!workspace && !error) return <section className="career-loading"><LoaderCircle className="spin" size={22} />正在读取求职计划</section>;

  return <div className="career-layout">
    <form className="career-panel" onSubmit={saveProfile}>
      <header><div><span>长期目标</span><h2>求职画像</h2></div>{workspace?.profile.confirmed_at && <small><Check size={13} />已确认</small>}</header>
      <p className="career-privacy-note">这里只保存你主动确认的目标；Agent 建议不会自动写入。</p>
      <div className="career-form-grid"><label><span>目标岗位</span><input required maxLength={150} value={profile.target_role} onChange={(event) => setProfile({ ...profile, target_role: event.target.value })} /></label><label><span>目标级别</span><input maxLength={50} value={profile.target_level} onChange={(event) => setProfile({ ...profile, target_level: event.target.value })} /></label><label><span>目标公司</span><input value={profile.target_companies} onChange={(event) => setProfile({ ...profile, target_companies: event.target.value })} placeholder="用逗号分隔" /></label><label><span>意向城市</span><input value={profile.preferred_cities} onChange={(event) => setProfile({ ...profile, preferred_cities: event.target.value })} placeholder="用逗号分隔" /></label><label><span>每周投入（小时）</span><input type="number" min={1} max={80} value={profile.weekly_hours} onChange={(event) => setProfile({ ...profile, weekly_hours: Number(event.target.value) })} /></label><label className="career-wide"><span>现实约束</span><textarea maxLength={2000} value={profile.constraints} onChange={(event) => setProfile({ ...profile, constraints: event.target.value })} placeholder="例如：工作日晚间最多 1 小时、暂不考虑异地" /></label></div>
      <button className="primary-cta" disabled={saving === "profile"} type="submit">{saving === "profile" ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}确认并保存画像</button>
    </form>

    <form className="career-panel weekly-plan-panel" onSubmit={savePlan}>
      <header><div><span>本周行动</span><h2>周计划</h2></div><label><span>周一</span><input type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} /></label></header>
      {workspace?.suggested_focus && <div className="suggested-focus"><span>根据已确认训练证据建议</span><p>{workspace.suggested_focus}</p></div>}
      <label className="plan-goal"><span>本周目标</span><input required maxLength={500} value={goal} onChange={(event) => setGoal(event.target.value)} /></label>
      <div className="plan-items">{items.map((item) => <article key={item.id}><select value={item.category} onChange={(event) => updateItem(item.id, { category: event.target.value as WeeklyPlanItem["category"] })}>{Object.entries(categoryLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><input aria-label="计划事项" required maxLength={200} value={item.title} onChange={(event) => updateItem(item.id, { title: event.target.value })} placeholder="具体行动" /><label><span>进度</span><input type="number" min={0} max={item.target_count} value={item.completed_count} onChange={(event) => updateItem(item.id, { completed_count: Math.min(item.target_count, Number(event.target.value)) })} /><i>/</i><input aria-label="目标数量" type="number" min={1} max={100} value={item.target_count} onChange={(event) => updateItem(item.id, { target_count: Math.max(1, Number(event.target.value)), completed_count: Math.min(item.completed_count, Math.max(1, Number(event.target.value))) })} /></label><button type="button" title="删除事项" aria-label="删除计划事项" onClick={() => setItems((current) => current.filter((entry) => entry.id !== item.id))}><Trash2 size={15} /></button></article>)}</div>
      <button className="plan-add" type="button" onClick={addItem}><Plus size={15} />添加行动</button>
      <button className="primary-cta" disabled={saving === "plan" || items.length === 0} type="submit">{saving === "plan" ? <LoaderCircle className="spin" size={15} /> : <Save size={15} />}保存本周计划</button>
    </form>
    {message && <p className="career-message">{message}</p>}{error && <p className="career-error" role="alert">{error}</p>}
  </div>;
}

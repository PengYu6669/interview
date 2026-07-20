"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  RefreshCw,
  Server,
  Wrench,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { adminLogListSchema, type AdminLog } from "@/lib/admin";

const toolLabels: Record<string, string> = {
  retrieve_candidate_context: "候选人资料检索",
  retrieve_job_context: "岗位资料检索",
  retrieve_job_evidence: "岗位证据检索",
  retrieve_public_knowledge: "公共知识检索",
};

function toolLabel(name: string) {
  return toolLabels[name] ?? name.replaceAll("_", " ");
}

function formatDate(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(value: number) {
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value} ms`;
}

export function AdminLogViewer() {
  const [logs, setLogs] = useState<AdminLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const loadLogs = useCallback(async (isRefresh = false) => {
    setError("");
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const response = await fetch("/api/admin/logs", { cache: "no-store" });
      const payload: unknown = await response.json();
      if (!response.ok) {
        throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "系统日志读取失败");
      }
      setLogs(adminLogListSchema.parse(payload));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "系统日志读取失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadLogs(), 0);
    return () => window.clearTimeout(timer);
  }, [loadLogs]);

  const summary = useMemo(() => {
    const total = logs.length;
    const successful = logs.filter((log) => log.succeeded).length;
    const failures = total - successful;
    const average = total === 0 ? 0 : Math.round(logs.reduce((sum, log) => sum + log.duration_ms, 0) / total);
    const tools = new Map<string, number>();
    logs.forEach((log) => tools.set(log.tool_name, (tools.get(log.tool_name) ?? 0) + 1));
    return {
      total,
      successful,
      failures,
      average,
      successRate: total === 0 ? 0 : Math.round((successful / total) * 100),
      tools: [...tools.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4),
      latest: logs[0],
    };
  }, [logs]);

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <SiteHeader active="admin" />
      <main className="mx-auto w-full max-w-[1240px] px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Operations</span>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">运行审计</h1>
            <p className="mt-1 text-sm text-[var(--muted)]">AI 工具调用的可靠性与延迟概览</p>
          </div>
          <button className="inline-flex h-9 items-center justify-center gap-2 border border-[var(--line)] bg-white px-3 text-sm font-medium transition hover:border-[var(--line-strong)] disabled:opacity-60" disabled={loading || refreshing} onClick={() => void loadLogs(true)} type="button">
            <RefreshCw className={refreshing ? "animate-spin" : ""} size={15} />
            刷新数据
          </button>
        </header>

        {error && <p className="mt-5 rounded-md border border-[var(--danger-border)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger)]" role="alert">{error}</p>}

        {loading ? (
          <div className="mt-6 grid min-h-64 place-items-center rounded-md bg-white text-[var(--muted)]"><RefreshCw className="animate-spin" size={20} /></div>
        ) : (
          <>
            <section aria-label="运行指标" className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard icon={<Activity size={17} />} label="调用总量" value={summary.total.toLocaleString("zh-CN")} detail="当前数据窗口" />
              <MetricCard icon={<CheckCircle2 size={17} />} label="成功率" value={`${summary.successRate}%`} detail={`${summary.successful} 次成功`} tone="success" />
              <MetricCard icon={<Clock3 size={17} />} label="平均耗时" value={formatDuration(summary.average)} detail="所有已记录调用" />
              <MetricCard icon={<AlertTriangle size={17} />} label="异常事件" value={summary.failures.toLocaleString("zh-CN")} detail={summary.failures ? "需要关注" : "暂无异常"} tone={summary.failures ? "danger" : "success"} />
            </section>

            <section className="mt-3 grid gap-3 lg:grid-cols-[1fr_320px]">
              <div className="rounded-md bg-white p-5 shadow-[var(--shadow-soft)]">
                <div className="flex items-start justify-between gap-4">
                  <div><h2 className="text-base font-semibold">最近运行事件</h2><p className="mt-1 text-xs text-[var(--muted)]">按时间倒序 · 最多展示 100 条记录</p></div>
                  <span className="inline-flex items-center gap-1.5 text-xs text-[var(--success)]"><span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />审计采集正常</span>
                </div>
                {logs.length === 0 ? <div className="grid min-h-40 place-items-center text-sm text-[var(--muted)]">暂无运行记录</div> : <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[680px] text-left text-sm"><thead className="border-b border-[var(--line)] text-xs text-[var(--muted)]"><tr><th className="pb-3 font-medium">事件</th><th className="pb-3 font-medium">状态</th><th className="pb-3 font-medium">耗时</th><th className="pb-3 text-right font-medium">时间</th></tr></thead><tbody>{logs.map((log) => <tr className="border-b border-[var(--border-light)] last:border-0" key={log.id}><td className="py-3"><div className="flex items-center gap-2"><span className={log.succeeded ? "text-[var(--success)]" : "text-[var(--danger)]"}>{log.succeeded ? <CheckCircle2 size={16} /> : <XCircle size={16} />}</span><div><strong className="font-medium">{toolLabel(log.tool_name)}</strong><span className="mt-0.5 block font-mono text-[11px] text-[var(--muted)]">{log.request_id.slice(0, 8)}</span></div></div></td><td className="py-3"><span className={log.succeeded ? "text-[var(--success)]" : "text-[var(--danger)]"}>{log.succeeded ? "成功" : `失败 · ${log.error_type ?? "未知错误"}`}</span></td><td className="py-3 font-mono text-xs text-[var(--muted)]">{formatDuration(log.duration_ms)}</td><td className="py-3 text-right text-xs text-[var(--muted)]"><time>{formatDate(log.created_at)}</time></td></tr>)}</tbody></table></div>}
              </div>

              <aside className="space-y-3">
                <div className="rounded-md bg-white p-5 shadow-[var(--shadow-soft)]"><div className="flex items-center gap-2"><Server size={17} /><h2 className="text-base font-semibold">运行状态</h2></div><div className="mt-4 space-y-3 text-sm"><StatusRow label="审计写入" value="正常" /><StatusRow label="最近事件" value={summary.latest ? formatDate(summary.latest.created_at) : "暂无"} /><StatusRow label="数据范围" value="最近 100 条" /></div></div>
                <div className="rounded-md bg-white p-5 shadow-[var(--shadow-soft)]"><div className="flex items-center gap-2"><Wrench size={17} /><h2 className="text-base font-semibold">工具调用分布</h2></div>{summary.tools.length === 0 ? <p className="mt-4 text-sm text-[var(--muted)]">暂无运行记录</p> : <div className="mt-4 space-y-3">{summary.tools.map(([name, count]) => <div key={name}><div className="mb-1 flex justify-between gap-3 text-xs"><span className="truncate">{toolLabel(name)}</span><span className="font-mono text-[var(--muted)]">{count}</span></div><div className="h-1.5 bg-[var(--bg-subtle)]"><div className="h-full bg-[var(--accent)]" style={{ width: `${Math.max(8, (count / summary.total) * 100)}%` }} /></div></div>)}</div>}</div>
              </aside>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

function MetricCard({ icon, label, value, detail, tone = "default" }: { icon: React.ReactNode; label: string; value: string; detail: string; tone?: "default" | "success" | "danger" }) {
  const toneClass = tone === "danger" ? "text-[var(--danger)]" : tone === "success" ? "text-[var(--success)]" : "text-[var(--ink)]";
  return <div className="rounded-md bg-white p-5 shadow-[var(--shadow-soft)]"><div className="flex items-center gap-2 text-xs text-[var(--muted)]">{icon}{label}</div><div className={`mt-3 text-2xl font-semibold tracking-tight ${toneClass}`}>{value}</div><div className="mt-1 text-xs text-[var(--muted)]">{detail}</div></div>;
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-3"><span className="text-[var(--muted)]">{label}</span><span className="inline-flex items-center gap-1.5 font-medium"><span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" />{value}</span></div>;
}

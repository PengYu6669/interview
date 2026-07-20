"use client";

import { CheckCircle2, CircleAlert, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { adminLogListSchema, type AdminLog } from "@/lib/admin";

export function AdminLogViewer() {
  const [logs, setLogs] = useState<AdminLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    void fetch("/api/admin/logs", { cache: "no-store" }).then(async (response) => {
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "系统日志读取失败");
      return adminLogListSchema.parse(payload);
    }).then(setLogs).catch((reason) => setError(reason instanceof Error ? reason.message : "系统日志读取失败")).finally(() => setLoading(false));
  }, []);

  return <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]"><SiteHeader active="admin" /><main className="mx-auto w-full max-w-[1180px] px-4 py-8 sm:px-6 lg:px-8"><header><span className="text-xs font-semibold text-[var(--muted)]">系统后台</span><h1 className="mt-1 text-2xl font-semibold">系统日志</h1></header>{error && <p className="mt-4 rounded-md bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger)]" role="alert">{error}</p>}<section className="mt-6 overflow-hidden rounded-md bg-white shadow-[var(--shadow-soft)]">{loading ? <div className="grid min-h-48 place-items-center text-[var(--muted)]"><LoaderCircle className="spin" size={18} /></div> : logs.length === 0 ? <div className="grid min-h-48 place-items-center text-sm text-[var(--muted)]">暂无系统日志</div> : <div className="divide-y divide-[var(--line)]">{logs.map((log) => <article className="grid gap-2 px-4 py-4 text-sm sm:grid-cols-[1fr_auto] sm:px-5" key={log.id}><div className="flex items-center gap-2"><span className={log.succeeded ? "text-[var(--success)]" : "text-[var(--danger)]"}>{log.succeeded ? <CheckCircle2 size={16} /> : <CircleAlert size={16} />}</span><strong>{log.tool_name}</strong><span className="text-xs text-[var(--muted)]">{log.succeeded ? "成功" : `失败 · ${log.error_type ?? "未知错误"}`}</span></div><div className="text-xs text-[var(--muted)] sm:text-right"><span>{log.duration_ms} ms</span><span className="mx-2">·</span><time>{new Date(log.created_at).toLocaleString("zh-CN")}</time><span className="block font-mono text-[11px]">请求 {log.request_id}</span></div></article>)}</div>}</section></main></div>;
}

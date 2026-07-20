"use client";

import { Activity, LoaderCircle, Search, ShieldCheck, UserPlus, UserRound, UsersRound } from "lucide-react";
import { useEffect, useState } from "react";

import { SiteHeader } from "@/components/site-header";
import { adminUserListSchema, type AdminUser, type AdminUserMetrics } from "@/lib/admin";

const emptyMetrics: AdminUserMetrics = {
  total_users: 0,
  daily_active_users: 0,
  weekly_active_users: 0,
  new_users_today: 0,
  admin_users: 0,
  timezone: "Asia/Shanghai",
};

export function AdminUserManager() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [metrics, setMetrics] = useState<AdminUserMetrics>(emptyMetrics);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void fetch(`/api/admin/users?query=${encodeURIComponent(query)}`, { cache: "no-store", signal: controller.signal })
        .then(async (response) => {
          const payload: unknown = await response.json();
          if (!response.ok) throw new Error(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : "用户列表读取失败");
          return adminUserListSchema.parse(payload);
        })
        .then((result) => { setUsers(result.users); setMetrics(result.metrics); })
        .catch((reason) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "用户列表读取失败"); })
        .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    }, 180);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [query]);

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <SiteHeader active="admin" />
      <main className="mx-auto w-full max-w-[1180px] px-4 py-8 sm:px-6 lg:px-8">
        <header><span className="text-xs font-semibold text-[var(--muted)]">系统后台</span><h1 className="mt-1 text-2xl font-semibold">用户管理</h1></header>
        <section aria-label="用户指标" className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric icon={<UsersRound size={17} />} label="用户总数" value={metrics.total_users} detail={`${metrics.admin_users} 位管理员`} />
          <Metric icon={<Activity size={17} />} label="今日活跃" value={metrics.daily_active_users} detail="截至当前" />
          <Metric icon={<UserRound size={17} />} label="近 7 日活跃" value={metrics.weekly_active_users} detail="去重用户" />
          <Metric icon={<UserPlus size={17} />} label="今日新增" value={metrics.new_users_today} detail="Asia/Shanghai" />
        </section>
        <label className="mt-6 flex h-10 max-w-sm items-center gap-2 rounded-md bg-white px-3 shadow-[var(--shadow-soft)]">
          <Search size={15} className="text-[var(--muted)]" /><span className="sr-only">搜索用户</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索用户名或邮箱" className="min-w-0 flex-1 bg-transparent text-sm outline-none" />
        </label>
        {error && <p className="mt-4 rounded-md bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger)]" role="alert">{error}</p>}
        <section className="mt-5 overflow-hidden rounded-md bg-white shadow-[var(--shadow-soft)]">
          {loading ? <div className="grid min-h-48 place-items-center text-[var(--muted)]"><LoaderCircle className="spin" size={18} /></div> : users.length === 0 ? <div className="grid min-h-48 place-items-center text-sm text-[var(--muted)]">没有匹配的用户</div> : <div className="divide-y divide-[var(--line)]">{users.map((user) => <article className="flex flex-wrap items-center gap-3 px-4 py-4 sm:px-5" key={user.id}><span className="grid size-9 place-items-center rounded-full bg-[var(--bg-subtle)] text-[var(--muted)]"><UserRound size={17} /></span><div className="min-w-0 flex-1"><strong className="block truncate text-sm">{user.username}</strong><span className="block truncate text-xs text-[var(--muted)]">{user.email}</span></div><span className="inline-flex items-center gap-1 rounded-full bg-[var(--bg-subtle)] px-2.5 py-1 text-xs text-[var(--muted)]">{user.role === "admin" ? <ShieldCheck size={13} /> : null}{user.role === "admin" ? "管理员" : "普通用户"}</span><time className="w-full text-xs text-[var(--muted)] sm:w-auto">注册于 {new Date(user.created_at).toLocaleDateString("zh-CN")}</time></article>)}</div>}
        </section>
      </main>
    </div>
  );
}

function Metric({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: number; detail: string }) {
  return <div className="rounded-md bg-white p-5 shadow-[var(--shadow-soft)]"><div className="flex items-center gap-2 text-xs text-[var(--muted)]">{icon}{label}</div><strong className="mt-3 block text-2xl font-semibold">{value.toLocaleString("zh-CN")}</strong><span className="mt-1 block text-xs text-[var(--muted)]">{detail}</span></div>;
}

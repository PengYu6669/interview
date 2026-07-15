"use client";

import {
  AlertTriangle,
  BookOpenCheck,
  Check,
  Database,
  Download,
  FileJson,
  FileStack,
  LoaderCircle,
  LogOut,
  MessageSquareText,
  ShieldCheck,
  Trash2,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { PageIntro } from "@/components/page-shell";
import { AccountDataSummary, accountDataSummarySchema } from "@/lib/account";

function responseError(payload: unknown, fallback: string) {
  return typeof payload === "object" && payload && "detail" in payload
    ? String(payload.detail)
    : fallback;
}

export function AccountCenter() {
  const router = useRouter();
  const [summary, setSummary] = useState<AccountDataSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportMessage, setExportMessage] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    let active = true;
    void fetch("/api/account", { cache: "no-store" })
      .then(async (response) => {
        const payload: unknown = await response.json();
        if (response.status === 401) {
          router.replace("/login?next=/account");
          return;
        }
        if (!response.ok) throw new Error(responseError(payload, "账号数据读取失败"));
        if (active) setSummary(accountDataSummarySchema.parse(payload));
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "账号数据读取失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router]);

  async function logout() {
    setLoggingOut(true);
    setActionError("");
    try {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error("退出登录失败，请稍后重试");
      window.location.href = "/";
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "退出登录失败");
      setLoggingOut(false);
    }
  }

  async function exportData() {
    setExporting(true);
    setExportMessage("");
    setActionError("");
    try {
      const response = await fetch("/api/account/export", { cache: "no-store" });
      if (response.status === 401) {
        router.replace("/login?next=/account");
        return;
      }
      if (!response.ok) {
        const payload: unknown = await response.json().catch(() => null);
        throw new Error(responseError(payload, "账号数据暂时无法导出"));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `interview-copilot-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setExportMessage("数据副本已生成并开始下载");
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "账号数据暂时无法导出");
    } finally {
      setExporting(false);
    }
  }

  async function deleteAccount() {
    if (!summary || deleteConfirmation !== summary.account.username) {
      setActionError("请输入完整账号名确认删除");
      return;
    }
    setDeleting(true);
    setActionError("");
    try {
      const response = await fetch("/api/account", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: deletePassword }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) throw new Error(responseError(payload, "账号注销失败"));
      window.location.href = "/?account=deleted";
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "账号注销失败");
      setDeleting(false);
    }
  }

  if (loading) return <main className="content-container account-page"><section className="account-loading"><LoaderCircle className="spin" size={25} /><strong>正在读取账号数据</strong><span>只汇总当前登录账号的数据</span></section></main>;
  if (error || !summary) return <main className="content-container account-page"><section className="account-loading error" role="alert"><AlertTriangle size={25} /><strong>账号数据读取失败</strong><span>{error || "请稍后重试"}</span><button type="button" className="secondary-button" onClick={() => window.location.reload()}>重新加载</button></section></main>;

  const joinedAt = new Intl.DateTimeFormat("zh-CN", { dateStyle: "long" }).format(new Date(summary.account.created_at));
  const metrics = [
    { label: "训练草稿", value: summary.draft_count, icon: FileStack },
    { label: "模拟面试", value: summary.interview_count, icon: MessageSquareText, href: "/history" },
    { label: "复盘报告", value: summary.report_count, icon: ShieldCheck, href: "/history" },
    { label: "个人题目", value: summary.private_question_count, icon: BookOpenCheck, href: "/questions" },
    { label: "学习笔记", value: summary.note_count, icon: BookOpenCheck, href: "/questions" },
  ];
  const deleteSummary = `${summary.draft_count} 份草稿、${summary.interview_count} 场面试、${summary.report_count} 份报告、${summary.private_question_count} 道个人题目和 ${summary.note_count} 条学习笔记`;
  const canDelete = deletePassword.length > 0 && deleteConfirmation === summary.account.username;

  return <main className="content-container account-page">
    <PageIntro eyebrow="账号与数据" title="管理你的训练空间" description="查看账号信息、导出训练数据，或永久删除当前账号及关联数据。" />
    <section className="account-identity"><div className="account-avatar"><UserRound size={27} /></div><div><span>当前账号</span><h2>{summary.account.username}</h2><p>{summary.account.email} · {joinedAt} 加入</p></div><button type="button" className="secondary-button" disabled={loggingOut} onClick={() => void logout()}>{loggingOut ? <LoaderCircle className="spin" size={15} /> : <LogOut size={15} />}{loggingOut ? "正在退出" : "退出登录"}</button></section>
    {actionError && <div className="account-action-message error" role="alert"><AlertTriangle size={15} /><span>{actionError}</span></div>}
    {exportMessage && <div className="account-action-message success" role="status"><Check size={15} /><span>{exportMessage}</span></div>}
    <section className="account-metrics" aria-label="账号数据概览">{metrics.map(({ label, value, icon: Icon, href }) => href ? <Link href={href} key={label}><Icon size={17} /><span>{label}</span><strong>{value}</strong></Link> : <article key={label}><Icon size={17} /><span>{label}</span><strong>{value}</strong></article>)}</section>
    <div className="account-settings-grid">
      <section className="account-setting-panel account-export-panel"><div className="account-setting-heading"><div><FileJson size={18} /></div><span><strong>导出我的数据</strong><small>生成当前时刻的 JSON 副本</small></span></div><div className="account-export-scope"><span><Check size={13} />校正后的简历与训练草稿</span><span><Check size={13} />面试问答与复盘报告</span><span><Check size={13} />个人题目、笔记与题库问答</span></div><p className="account-sensitive-note"><AlertTriangle size={14} />导出文件包含简历文本和面试回答，请保存在可信设备，不要公开上传。</p><button className="primary-cta" type="button" disabled={exporting} onClick={() => void exportData()}>{exporting ? <LoaderCircle className="spin" size={15} /> : <Download size={15} />}{exporting ? "正在生成数据副本" : "下载 JSON 数据"}</button></section>
      <section className="account-setting-panel account-retention-panel"><div className="account-setting-heading"><div><Database size={18} /></div><span><strong>数据保存说明</strong><small>当前真实存储边界</small></span></div><dl className="retention-list"><div><dt>训练草稿</dt><dd>默认 7 天</dd></div><div><dt>面试与报告</dt><dd>保留至账号注销</dd></div><div><dt>完整录音</dt><dd>当前不保存</dd></div><div><dt>原始简历文件</dt><dd>解析后不保存</dd></div></dl><span className="account-policy-note">当前只保存校正后的简历文本与结构化结果，不启用 TOS 原文件存储。</span></section>
    </div>
    <section className={`account-danger-zone ${confirmingDelete ? "confirming" : ""}`}><div><span className="danger-icon"><Trash2 size={18} /></span><div><h2>永久注销账号</h2><p>将删除 {deleteSummary}。此操作无法撤销。</p></div></div>{!confirmingDelete ? <button type="button" onClick={() => { setConfirmingDelete(true); setActionError(""); }}>注销账号</button> : <div className="account-delete-form"><div className="delete-warning"><AlertTriangle size={15} /><span>请确认已经导出需要保留的数据。删除后无法恢复。</span></div><label>输入账号名 <strong>{summary.account.username}</strong><input value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} autoComplete="off" spellCheck={false} /></label><label>输入当前密码<input value={deletePassword} onChange={(event) => setDeletePassword(event.target.value)} type="password" autoComplete="current-password" maxLength={128} /></label><div><button type="button" className="secondary-button" disabled={deleting} onClick={() => { setConfirmingDelete(false); setDeletePassword(""); setDeleteConfirmation(""); setActionError(""); }}>取消</button><button type="button" className="account-delete-submit" disabled={deleting || !canDelete} onClick={() => void deleteAccount()}>{deleting ? <LoaderCircle className="spin" size={14} /> : <Trash2 size={14} />}{deleting ? "正在永久删除" : "确认永久删除"}</button></div></div>}</section>
  </main>;
}

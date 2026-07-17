"use client";

import { ArrowLeft, ArrowRight, Eye, EyeOff, LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

type AuthField = "username" | "email" | "identifier" | "password" | "password_confirm";
type FieldErrors = Partial<Record<AuthField, string>>;

export function AuthPage({ mode, nextPath = "/training" }: { mode: "login" | "register"; nextPath?: string }) {
  const registering = mode === "register";
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  function clearField(name: AuthField) {
    setFieldErrors((current) => current[name] ? { ...current, [name]: undefined } : current);
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFieldErrors({});
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    const username = String(form.get("username") ?? "").trim();
    const errors: FieldErrors = {};
    if (registering) {
      if (!/^[\p{L}\p{N}_]{3,50}$/u.test(username)) errors.username = "请输入 3 至 50 位文字、字母、数字或下划线";
      const email = String(form.get("email") ?? "").trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = "请输入有效邮箱地址";
      if (password.length < 6) errors.password = "密码至少需要 6 位";
      if (new TextEncoder().encode(password).length > 128) errors.password = "密码过长，请控制在 128 字节以内";
      if (password !== String(form.get("password_confirm") ?? "")) errors.password_confirm = "两次输入的密码不一致";
    } else {
      if (!String(form.get("identifier") ?? "").trim()) errors.identifier = "请输入用户名或邮箱";
      if (!password) errors.password = "请输入密码";
    }
    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      const first = Object.keys(errors)[0] as AuthField;
      const target = event.currentTarget.elements.namedItem(first);
      if (target instanceof HTMLElement) target.focus();
      return;
    }
    const payload = registering
      ? { username, email: String(form.get("email") ?? ""), password }
      : { identifier: String(form.get("identifier") ?? ""), password };
    setSubmitting(true);
    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result: unknown = await response.json();
      if (!response.ok) {
        const detail = typeof result === "object" && result !== null && "detail" in result ? String(result.detail) : "账号操作失败";
        throw new Error(detail);
      }
      router.replace(nextPath);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "账号操作失败");
    } finally {
      setSubmitting(false);
    }
  }

  return <main className="auth-page">
    <section className="auth-intro"><Link href="/" className="back-link"><ArrowLeft size={15} />返回首页</Link><div><span className="brand-mark">面</span><p>InterviewCopilot</p></div><h1>{registering ? "创建你的训练空间" : "继续你的面试训练"}</h1><p>{registering ? "训练草稿默认保存 7 天；面试记录和复盘报告会保存到你主动注销账号。" : "使用用户名或邮箱登录，继续你的面试训练。"}</p></section>
    <section className="auth-form-shell"><div className="dialog-icon"><LockKeyhole size={20} /></div><h2>{registering ? "注册账号" : "账号登录"}</h2><p>{registering ? "用户名支持中文、字母、数字和下划线" : "登录后进入面试准备工作台"}</p><form method="post" onSubmit={submit} noValidate>{registering ? <><label>用户名<input name="username" type="text" autoComplete="username" required minLength={3} maxLength={50} placeholder="3 至 50 位" aria-invalid={Boolean(fieldErrors.username)} aria-describedby={fieldErrors.username ? "username-error" : undefined} onChange={() => clearField("username")} />{fieldErrors.username && <FieldError id="username-error">{fieldErrors.username}</FieldError>}</label><label>邮箱<input name="email" type="email" autoComplete="email" required maxLength={320} placeholder="name@example.com" aria-invalid={Boolean(fieldErrors.email)} aria-describedby={fieldErrors.email ? "email-error" : undefined} onChange={() => clearField("email")} />{fieldErrors.email && <FieldError id="email-error">{fieldErrors.email}</FieldError>}</label></> : <label>用户名或邮箱<input name="identifier" type="text" autoComplete="username" required maxLength={320} placeholder="请输入用户名或邮箱" aria-invalid={Boolean(fieldErrors.identifier)} aria-describedby={fieldErrors.identifier ? "identifier-error" : undefined} onChange={() => clearField("identifier")} />{fieldErrors.identifier && <FieldError id="identifier-error">{fieldErrors.identifier}</FieldError>}</label>}<PasswordField name="password" label="密码" autoComplete={registering ? "new-password" : "current-password"} minLength={registering ? 6 : 1} placeholder={registering ? "至少 6 位" : "请输入密码"} error={fieldErrors.password} onChange={() => clearField("password")} />{registering && <PasswordField name="password_confirm" label="确认密码" autoComplete="new-password" minLength={6} placeholder="再次输入密码" error={fieldErrors.password_confirm} onChange={() => clearField("password_confirm")} />}{error && <p className="auth-error" role="alert">{error}</p>}<button type="submit" disabled={submitting}>{submitting ? "正在处理…" : registering ? "创建账号" : "登录"}</button></form><div className="auth-switch">{registering ? <>已有账号？<Link href={`/login?next=${encodeURIComponent(nextPath)}`}>前往登录</Link></> : <>还没有账号？<Link href={`/register?next=${encodeURIComponent(nextPath)}`}>创建账号</Link></>}</div><Link href="/setup" className="text-link">暂不登录，查看面试准备流程 <ArrowRight size={14} /></Link></section>
  </main>;
}

function FieldError({ id, children }: { id: string; children: React.ReactNode }) {
  return <span className="auth-field-error" id={id} role="alert">{children}</span>;
}

function PasswordField({ name, label, autoComplete, minLength, placeholder, error, onChange }: { name: "password" | "password_confirm"; label: string; autoComplete: string; minLength: number; placeholder: string; error?: string; onChange: () => void }) {
  const [visible, setVisible] = useState(false);
  const errorId = `${name}-error`;
  return <label>{label}<span className="auth-password-field"><input name={name} type={visible ? "text" : "password"} autoComplete={autoComplete} required minLength={minLength} maxLength={128} placeholder={placeholder} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined} onChange={onChange} /><button type="button" onClick={() => setVisible((current) => !current)} title={visible ? "隐藏密码" : "显示密码"} aria-label={visible ? "隐藏密码" : "显示密码"}>{visible ? <EyeOff size={16} /> : <Eye size={16} />}</button></span>{error && <FieldError id={errorId}>{error}</FieldError>}</label>;
}

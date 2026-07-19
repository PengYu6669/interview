"use client";

import { ArrowLeft, ArrowRight, Eye, EyeOff, LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { authUserSchema } from "@/lib/auth";
import { useAuth } from "@/lib/auth-context";

type AuthField = "username" | "email" | "identifier" | "password" | "password_confirm";
type FieldErrors = Partial<Record<AuthField, string>>;

function FieldError({ id, children }: { id: string; children: React.ReactNode }) {
  return <span className="mt-1 block text-xs text-[var(--danger)]" id={id} role="alert">{children}</span>;
}

function PasswordField({ name, label, autoComplete, minLength, placeholder, error, onChange }: {
  name: "password" | "password_confirm";
  label: string; autoComplete: string; minLength: number; placeholder: string;
  error?: string; onChange: () => void;
}) {
  const [visible, setVisible] = useState(false);
  const errorId = `${name}-error`;
  return (
    <label className="grid gap-1.5">
      <span className="text-sm font-medium text-[var(--text-primary)]">{label}</span>
      <span className="flex rounded-lg border border-[var(--border-default)] bg-[var(--bg-canvas)] transition-colors duration-150 focus-within:border-[var(--accent)] focus-within:ring-1 focus-within:ring-[var(--accent-light)]">
        <input
          name={name}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          required minLength={minLength} maxLength={128}
          placeholder={placeholder}
          className="flex-1 border-0 bg-transparent px-4 py-3 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-placeholder)]"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : undefined}
          onChange={onChange}
        />
        <button type="button" className="m-1 grid size-10 place-items-center rounded-lg border-0 bg-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]" onClick={() => setVisible((v) => !v)} title={visible ? "隐藏密码" : "显示密码"} aria-label={visible ? "隐藏密码" : "显示密码"}>
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </span>
      {error && <FieldError id={errorId}>{error}</FieldError>}
    </label>
  );
}

export function AuthPage({ mode, nextPath = "/training" }: { mode: "login" | "register"; nextPath?: string }) {
  const registering = mode === "register";
  const router = useRouter();
  const { setAuthenticatedUser } = useAuth();
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
      const authenticatedUser = authUserSchema.safeParse(
        typeof result === "object" && result !== null && "user" in result
          ? (result as { user: unknown }).user
          : null,
      );
      if (!authenticatedUser.success) throw new Error("登录状态同步失败，请重试");
      setAuthenticatedUser(authenticatedUser.data);
      router.replace(nextPath);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "账号操作失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-dvh bg-[var(--bg-canvas)] lg:grid-cols-[minmax(0,1fr)_minmax(420px,0.75fr)]">
      <section className="flex min-h-[38dvh] flex-col px-6 py-7 sm:px-10 lg:min-h-dvh lg:px-[max(48px,calc((100vw-1180px)/2))] lg:py-12">
        <Link href="/" className="inline-flex w-fit items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--ink)]">
          <ArrowLeft size={15} />返回首页
        </Link>
        <div className="mt-auto pt-12">
          <span className="inline-grid size-10 place-items-center rounded-lg bg-[var(--text-primary)] text-sm font-semibold text-white">面</span>
          <p className="mt-3 text-sm font-semibold">InterviewCopilot</p>
          <h1 className="mt-3 text-balance text-3xl font-semibold leading-tight">
            {registering ? "创建你的训练空间" : "继续你的面试训练"}
          </h1>
          <p className="mt-2 max-w-[320px] text-[14px] leading-relaxed text-[var(--muted)]">
            {registering
              ? "训练草稿默认保存 7 天；面试记录和复盘报告会保存到你主动注销账号。"
              : "使用用户名或邮箱登录，继续你的面试训练。"}
          </p>
        </div>
      </section>

      <section className="flex flex-col justify-center border-t border-[var(--line)] bg-white px-6 py-12 sm:px-10 lg:border-l lg:border-t-0 lg:px-[max(40px,calc((100vw-1180px)/4))] lg:py-16">
        <div className="grid size-10 place-items-center rounded-lg bg-[var(--bg-subtle)] text-[var(--ink)]"><LockKeyhole size={20} /></div>
        <h2 className="mt-4 text-xl font-semibold">{registering ? "注册账号" : "账号登录"}</h2>
        <p className="mt-1 text-[13px] text-[var(--muted)]">
          {registering ? "用户名支持中文、字母、数字和下划线" : "登录后进入面试准备工作台"}
        </p>
        <form method="post" onSubmit={submit} noValidate className="mt-6 grid gap-4">
          {registering ? (
            <>
              <label className="grid gap-1.5">
                <span className="text-sm font-medium text-[var(--text-primary)]">用户名</span>
                <input name="username" type="text" autoComplete="username" required minLength={3} maxLength={50}
                  placeholder="3 至 50 位" className="h-11 rounded-lg border border-[var(--border-default)] bg-[var(--bg-canvas)] px-4 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-placeholder)] focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent-light)]"
                  aria-invalid={Boolean(fieldErrors.username)}
                  aria-describedby={fieldErrors.username ? "username-error" : undefined}
                  onChange={() => clearField("username")} />
                {fieldErrors.username && <FieldError id="username-error">{fieldErrors.username}</FieldError>}
              </label>
              <label className="grid gap-1.5">
                <span className="text-sm font-medium text-[var(--text-primary)]">邮箱</span>
                <input name="email" type="email" autoComplete="email" required maxLength={320}
                  placeholder="name@example.com" className="h-11 rounded-lg border border-[var(--border-default)] bg-[var(--bg-canvas)] px-4 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-placeholder)] focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent-light)]"
                  aria-invalid={Boolean(fieldErrors.email)}
                  aria-describedby={fieldErrors.email ? "email-error" : undefined}
                  onChange={() => clearField("email")} />
                {fieldErrors.email && <FieldError id="email-error">{fieldErrors.email}</FieldError>}
              </label>
            </>
          ) : (
            <label className="grid gap-1.5">
              <span className="text-sm font-medium text-[var(--text-primary)]">用户名或邮箱</span>
              <input name="identifier" type="text" autoComplete="username" required maxLength={320}
                placeholder="请输入用户名或邮箱" className="h-11 rounded-lg border border-[var(--border-default)] bg-[var(--bg-canvas)] px-4 text-sm text-[var(--text-primary)] outline-none placeholder:text-[var(--text-placeholder)] focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent-light)]"
                aria-invalid={Boolean(fieldErrors.identifier)}
                aria-describedby={fieldErrors.identifier ? "identifier-error" : undefined}
                onChange={() => clearField("identifier")} />
              {fieldErrors.identifier && <FieldError id="identifier-error">{fieldErrors.identifier}</FieldError>}
            </label>
          )}
          <PasswordField name="password" label="密码"
            autoComplete={registering ? "new-password" : "current-password"}
            minLength={registering ? 6 : 1}
            placeholder={registering ? "至少 6 位" : "请输入密码"}
            error={fieldErrors.password} onChange={() => clearField("password")} />
          {registering && (
            <PasswordField name="password_confirm" label="确认密码"
              autoComplete="new-password" minLength={6} placeholder="再次输入密码"
              error={fieldErrors.password_confirm} onChange={() => clearField("password_confirm")} />
          )}
          {error && <p className="rounded-lg border border-[var(--danger-border)] bg-[var(--danger-bg)] px-4 py-3 text-sm text-[var(--danger)]" role="alert">{error}</p>}
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "正在处理…" : registering ? "创建账号" : "登录"}
          </Button>
        </form>
        <div className="mt-4 text-center text-[13px] text-[var(--muted)]">
          {registering ? <>已有账号？<Link className="font-semibold text-[var(--accent-dark)] hover:underline" href={`/login?next=${encodeURIComponent(nextPath)}`}>前往登录</Link></>
          : <>还没有账号？<Link className="font-semibold text-[var(--accent-dark)] hover:underline" href={`/register?next=${encodeURIComponent(nextPath)}`}>创建账号</Link></>}
        </div>
        <Link href="/setup" className="mt-3 inline-flex items-center gap-1.5 text-[13px] text-[var(--muted)] hover:text-[var(--ink)]">
          暂不登录，查看面试准备流程 <ArrowRight size={14} />
        </Link>
      </section>
    </main>
  );
}

"use client";

import { ChartNoAxesCombined, GraduationCap, LibraryBig, LogOut, Menu, ShieldCheck, UserRound, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export type ActivePage = "new" | "training" | "questions" | "history" | "profile" | "account" | "admin";

const navigation: Array<{ key: string; href: string; label: string; icon: typeof LibraryBig; active: ActivePage[] }> = [
  { key: "questions", href: "/questions", label: "学习中心", icon: LibraryBig, active: ["questions"] },
  { key: "training", href: "/training", label: "训练中心", icon: GraduationCap, active: ["new", "training"] },
  { key: "growth", href: "/history", label: "成长档案", icon: ChartNoAxesCombined, active: ["history", "profile"] },
];

const adminNavigation = [
  { key: "admin-questions", href: "/admin/questions", label: "题库管理", icon: ShieldCheck, active: ["admin"] as ActivePage[] },
  { key: "admin-users", href: "/admin/users", label: "用户管理", icon: UserRound, active: ["admin"] as ActivePage[] },
  { key: "admin-logs", href: "/admin/logs", label: "系统日志", icon: ChartNoAxesCombined, active: ["admin"] as ActivePage[] },
];

export function SiteHeader({ active }: { active: ActivePage }) {
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [open]);

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link href={user ? (user.role === "admin" ? "/admin/questions" : "/training") : "/"} className="brand-link" aria-label={user ? (user.role === "admin" ? "进入题库管理" : "进入今日训练") : "InterviewCopilot 首页"}>
          <span className="brand-mark">面</span>
          <span>
            <span className="brand-name">InterviewCopilot</span>
            <span className="brand-subtitle">面壁 · 技术面试训练</span>
          </span>
        </Link>
        <nav className="desktop-nav" aria-label="主导航">
          {(user?.role === "admin" ? adminNavigation : navigation).map(({ key, href, label, icon: Icon, active: activePages }) => (
            <Link className={`nav-link ${activePages.includes(active) ? "nav-link-active" : ""}`} href={href} key={key}>
              <Icon size={16} />{label}
            </Link>
          ))}
          {user ? <><Link className={`nav-user ${active === "account" ? "nav-user-active" : ""}`} href="/account"><UserRound size={15} />{user.username}</Link><TooltipProvider delayDuration={300}><Tooltip><TooltipTrigger asChild><Button type="button" variant="ghost" size="icon" onClick={logout} aria-label="退出登录"><LogOut size={16} /></Button></TooltipTrigger><TooltipContent>退出登录</TooltipContent></Tooltip></TooltipProvider></> : <Button asChild variant="ghost" size="sm"><Link href="/login"><UserRound size={16} />登录</Link></Button>}
        </nav>
        <button className="mobile-menu-button" type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-label={open ? "关闭导航" : "打开导航"}>
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>
      {open && (
        <nav className="mobile-nav" aria-label="移动端导航">
          {(user?.role === "admin" ? adminNavigation : navigation).map(({ key, href, label, icon: Icon, active: activePages }) => (
            <Link className={activePages.includes(active) ? "nav-link-active" : ""} href={href} key={key} onClick={() => setOpen(false)}>
              <Icon size={17} />{label}
            </Link>
          ))}
          {user ? <><Link className={active === "account" ? "nav-link-active" : ""} href="/account" onClick={() => setOpen(false)}><UserRound size={17} />账号与数据</Link><Button className="w-full justify-start text-[var(--danger)]" variant="ghost" onClick={logout}><LogOut size={17} />退出登录</Button></> : <Link href="/login" onClick={() => setOpen(false)}><UserRound size={17} />登录</Link>}
        </nav>
      )}
    </header>
  );
}

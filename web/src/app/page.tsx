import { ArrowRight, CheckCircle2, FileCheck2, History, Mic2, RefreshCw, ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";

import { currentUser } from "@/lib/auth-server";
import { Button } from "@/components/ui/button";

const capabilities = [
  { icon: FileCheck2, title: "材料先确认", text: "校正简历和岗位信息后再生成面试，不让错误解析带偏问题。" },
  { icon: Mic2, title: "实时语音追问", text: "围绕项目过程、技术取舍和故障处理继续深挖，也支持文字回答。" },
  { icon: RefreshCw, title: "中断可以恢复", text: "回答草稿和面试进度会保留，网络恢复后从当前问题继续。" },
];

export default async function Home({ searchParams }: { searchParams: Promise<{ account?: string }> }) {
  const accountDeleted = (await searchParams).account === "deleted";
  const user = await currentUser();
  if (user?.role === "admin") redirect("/admin/questions");

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      {/* Account deleted notice */}
      {accountDeleted && (
        <div className="flex items-center justify-center gap-2 bg-[var(--accent-soft)] px-4 py-2.5 text-sm text-[var(--accent-dark)]" role="status">
          <CheckCircle2 size={16} />
          <span>账号及关联数据已永久删除</span>
        </div>
      )}

      {/* Header */}
      <header className="mx-auto flex max-w-[1200px] items-center justify-between px-7 py-5">
        <Link href="/" className="flex items-center gap-2.5" aria-label="InterviewCopilot 首页">
          <span className="grid size-9 place-items-center rounded-lg bg-[var(--text-primary)] text-sm font-semibold text-white">面</span>
          <span className="text-sm font-semibold">InterviewCopilot</span>
        </Link>
        <nav className="hidden items-center gap-6 text-[13px] text-[var(--muted)] sm:flex" aria-label="首页导航">
          <a href="#interview" className="hover:text-[var(--ink)] transition-colors">模拟面试</a>
          <a href="#review" className="hover:text-[var(--ink)] transition-colors">训练复盘</a>
        </nav>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <Link href="/account" className="text-[13px] font-medium text-[var(--muted)] hover:text-[var(--ink)] transition-colors">
                {user.username}
              </Link>
              <Button size="sm" asChild>
                <Link href="/setup">开始面试 <ArrowRight size={15} /></Link>
              </Button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-[13px] font-medium text-[var(--muted)] hover:text-[var(--ink)] transition-colors">
                登录
              </Link>
              <Button size="sm" asChild>
                <Link href="/register">免费开始 <ArrowRight size={15} /></Link>
              </Button>
            </>
          )}
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto max-w-[1200px] px-7 pb-20 pt-12 sm:pt-20">
          <div className="grid items-center gap-12 lg:grid-cols-[1fr_auto] lg:gap-16">
            <div className="max-w-[560px]">
              <p className="inline-flex items-center gap-2 text-xs font-medium uppercase text-[var(--accent)]">
                <span className="block h-px w-8 bg-[var(--accent)]" />
                沉浸式 AI 模拟面试
              </p>
              <h1 className="mt-4 text-balance text-4xl font-semibold leading-tight">
                把真实项目，练成<br />
                <span className="text-[var(--accent)]">现场讲得清的回答</span>
              </h1>
              <p className="mt-4 max-w-[28rem] text-pretty text-lg leading-relaxed text-[var(--text-secondary)]">
                根据简历和目标岗位生成面试计划，在实时语音房间里回答、追问、暂停和恢复，结束后直接进入复盘。
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-3">
                {user ? (
                  <>
                    <Button size="lg" asChild>
                      <Link href="/setup">开始模拟面试 <ArrowRight size={17} /></Link>
                    </Button>
                    <Button variant="secondary" size="lg" asChild>
                      <Link href="/history">查看面试记录</Link>
                    </Button>
                  </>
                ) : (
                  <>
                    <Button size="lg" asChild>
                      <Link href="/register">创建训练账号 <ArrowRight size={17} /></Link>
                    </Button>
                    <Button variant="secondary" size="lg" asChild>
                      <Link href="/login">已有账号，登录</Link>
                    </Button>
                  </>
                )}
              </div>
              <div className="mt-6 flex flex-wrap gap-x-6 gap-y-1.5 text-xs text-[var(--muted)]">
                <span className="inline-flex items-center gap-1.5"><Mic2 size={13} />语音与文字均可回答</span>
                <span className="inline-flex items-center gap-1.5"><ShieldCheck size={13} />本轮草稿自动保留</span>
              </div>
            </div>

            <div id="interview" className="lg:w-[520px]">
              <div className="overflow-hidden rounded-lg border border-[var(--border-default)] bg-[#111] shadow-[var(--shadow-lift)]">
                <div className="flex items-center gap-2 border-b border-white/10 px-4 py-2.5 text-white">
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--ink)]">
                    <span className="block size-2 rounded-full bg-[var(--danger)]" />
                    <span className="text-white">实时模拟面试</span>
                  </span>
                  <span className="ml-auto text-xs text-white/50">项目深挖 · 第 2 题</span>
                </div>
                <Image
                  src="/interview-room-preview.png"
                  alt="深色实时模拟面试房间"
                  width={1280}
                  height={800}
                  className="aspect-[16/10] w-full object-cover grayscale contrast-125"
                  priority
                />
                <div className="grid grid-cols-3 border-t border-white/10 text-xs text-white/60">
                  <span className="flex min-h-10 items-center justify-center gap-1.5"><Mic2 size={13} />实时回答</span>
                  <span className="flex min-h-10 items-center justify-center gap-1.5 border-x border-white/10"><RefreshCw size={13} />暂停恢复</span>
                  <span className="flex min-h-10 items-center justify-center gap-1.5"><History size={13} />完成复盘</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Capabilities */}
        <section id="how-it-works" className="border-y border-[var(--line)] bg-white py-16 sm:py-24">
          <div className="mx-auto max-w-[1200px] px-7">
            <div className="mx-auto max-w-[480px] text-center">
              <p className="text-xs font-medium uppercase text-[var(--accent)]">完整面试流程</p>
              <h2 className="mt-2 text-balance text-2xl font-semibold">准备、回答、追问、复盘一次完成</h2>
            </div>
            <div className="mt-12 grid gap-5 sm:grid-cols-3">
              {capabilities.map(({ icon: Icon, title, text }, index) => (
                <article key={title} className="group rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-6 transition-[border-color,transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:border-[var(--border-hover)] hover:shadow-[var(--shadow-lift)]">
                  <span className="text-xs font-medium tabular-nums text-[var(--text-muted)]">0{index + 1}</span>
                  <div className="mt-3 grid size-10 place-items-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
                    <Icon size={20} />
                  </div>
                  <h3 className="mt-3 text-base font-medium">{title}</h3>
                  <p className="mt-1.5 text-pretty text-sm leading-relaxed text-[var(--text-secondary)]">{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* Review */}
        <section id="review" className="mx-auto max-w-[1200px] px-7 py-16 sm:py-24">
          <div className="grid items-center gap-12 lg:grid-cols-[1fr_1fr] lg:gap-16">
            <div>
              <p className="inline-flex items-center gap-2 text-xs font-medium uppercase text-[var(--accent)]">
                <span className="block h-px w-8 bg-[var(--accent)]" />
                面试结束后
              </p>
              <h2 className="mt-3 text-balance text-2xl font-semibold">下一次该练什么，直接从本场回答里看</h2>
              <p className="mt-3 max-w-[420px] text-[15px] leading-relaxed text-[var(--muted)]">
                复盘会区分内容缺失、表达不清和本场未考察，并把需要补练的方向带入能力画像与后续计划。
              </p>
            </div>
            <blockquote className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-6">
              <span className="text-xs font-medium uppercase text-[var(--accent)]">你的回答</span>
              <p className="mt-3 text-[15px] leading-relaxed">
                &ldquo;我用 LangGraph 重构了流程，因为原来的 Chain 难以恢复中断状态……&rdquo;
              </p>
              <footer className="mt-3 border-t border-[var(--line)] pt-3 text-[13px] leading-relaxed text-[var(--muted)]">
                改进方向：补充状态持久化方案，以及为什么没有选择普通任务队列。
              </footer>
            </blockquote>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--line)] bg-white">
        <div className="mx-auto flex max-w-[1200px] flex-col items-start gap-4 px-7 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span className="text-sm font-semibold">InterviewCopilot · 面壁</span>
            <p className="mt-1 max-w-[380px] text-[13px] leading-relaxed text-[var(--muted)]">
              从你的真实经历出发，完成一场可以持续复练的技术面试。
            </p>
          </div>
          <Button variant="secondary" asChild>
            <Link href={user ? "/setup" : "/register"}>
              {user ? "开始新训练" : "开始第一次训练"} <ArrowRight size={14} />
            </Link>
          </Button>
        </div>
      </footer>
    </div>
  );
}

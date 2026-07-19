import { ArrowRight, Bot, Check, CheckCircle2, FileSearch, ListChecks, Quote, SearchCheck, ShieldCheck, Target } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { currentUser } from "@/lib/auth-server";
import { Button } from "@/components/ui/button";

const capabilities = [
  { icon: FileSearch, title: "从你的经历出题", text: "先解析简历与岗位描述，再让你确认系统理解得是否正确。" },
  { icon: Target, title: "追问具体，而非背题", text: "围绕项目选择、故障处理和技术取舍继续深挖。" },
  { icon: Quote, title: "评价可以回到证据", text: "复盘引用你的原回答，区分能力不足、证据不足与未考察。" },
];

export default async function Home({ searchParams }: { searchParams: Promise<{ account?: string }> }) {
  const accountDeleted = (await searchParams).account === "deleted";
  const user = await currentUser();

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
          <a href="#how-it-works" className="hover:text-[var(--ink)] transition-colors">如何工作</a>
          <a href="#evidence" className="hover:text-[var(--ink)] transition-colors">证据化复盘</a>
        </nav>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <Link href="/account" className="text-[13px] font-medium text-[var(--muted)] hover:text-[var(--ink)] transition-colors">
                {user.username}
              </Link>
              <Button size="sm" asChild>
                <Link href="/training">今日训练 <ArrowRight size={15} /></Link>
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
                针对真实经历的技术面试训练
              </p>
              <h1 className="mt-4 text-balance text-4xl font-semibold leading-tight">
                不是再做一套题，<br />
                而是练会<span className="text-[var(--accent)]">讲清你的项目</span>
              </h1>
              <p className="mt-4 max-w-[28rem] text-pretty text-lg leading-relaxed text-[var(--text-secondary)]">
                上传简历和目标岗位，先校正 AI 对你的理解，再进入一场接近真实视频会议节奏的模拟技术面试。
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-3">
                {user ? (
                  <>
                    <Button size="lg" asChild>
                      <Link href="/training">查看今日教练建议 <ArrowRight size={17} /></Link>
                    </Button>
                    <Button variant="secondary" size="lg" asChild>
                      <Link href="/history">回看成长档案</Link>
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
                <span className="inline-flex items-center gap-1.5"><ShieldCheck size={13} />材料默认保留 7 天</span>
                <span className="inline-flex items-center gap-1.5"><CheckCircle2 size={13} />评价附带回答证据</span>
              </div>
            </div>

            {/* Product screenshot */}
            <div className="relative lg:w-[520px]">
              <div className="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)]">
                <div className="flex items-center gap-2 border-b border-[var(--line)] px-4 py-2.5">
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-[var(--ink)]">
                    <span className="block size-2 rounded-full bg-[var(--danger)]" />
                    模拟面试进行中
                  </span>
                  <span className="ml-auto text-[11px] text-[var(--muted)]">真实产品界面</span>
                </div>
                <Image
                  src="/interview-room-preview.png"
                  alt="InterviewCopilot 模拟视频面试室界面"
                  width={1280}
                  height={800}
                  className="w-full"
                  priority
                />
              </div>

              {/* AI trace card */}
              <div className="absolute -bottom-4 -left-4 right-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-5" aria-label="AI 面试教练工作轨迹示意">
                <div className="flex items-center gap-2.5">
                  <span className="grid size-8 place-items-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
                    <Bot size={17} />
                  </span>
                  <div>
                    <span className="text-[13px] font-semibold">AI 工作轨迹</span>
                    <span className="ml-2 rounded-full border border-[var(--danger-border)] bg-[var(--danger-bg)] px-2 py-1 text-xs font-medium text-[var(--danger)]">LIVE</span>
                  </div>
                </div>
                <ol className="mt-3 grid gap-1.5">
                  <li className="flex items-center gap-2 text-xs text-[var(--muted)]">
                    <Check size={13} className="text-[var(--accent)]" />
                    <span>读取简历与 JD</span>
                    <span className="ml-auto text-[11px]">完成</span>
                  </li>
                  <li className="flex items-center gap-2 text-xs font-medium text-[var(--ink)]">
                    <SearchCheck size={13} className="text-[var(--accent-muted)]" />
                    <span>匹配回答证据</span>
                    <span className="ml-auto text-xs text-[var(--accent)]">进行中</span>
                  </li>
                  <li className="flex items-center gap-2 text-xs text-[var(--muted)]">
                    <ListChecks size={13} />
                    <span>更新追问计划</span>
                    <span className="ml-auto text-[11px]">下一步</span>
                  </li>
                </ol>
              </div>
            </div>
          </div>
        </section>

        {/* Capabilities */}
        <section id="how-it-works" className="border-y border-[var(--line)] bg-white py-16 sm:py-24">
          <div className="mx-auto max-w-[1200px] px-7">
            <div className="mx-auto max-w-[480px] text-center">
              <p className="text-xs font-medium uppercase text-[var(--accent)]">训练链路</p>
              <h2 className="mt-2 text-balance text-2xl font-semibold">从材料到复盘，每一步都让你确认</h2>
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

        {/* Evidence */}
        <section id="evidence" className="mx-auto max-w-[1200px] px-7 py-16 sm:py-24">
          <div className="grid items-center gap-12 lg:grid-cols-[1fr_1fr] lg:gap-16">
            <div>
              <p className="inline-flex items-center gap-2 text-xs font-medium uppercase text-[var(--accent)]">
                <span className="block h-px w-8 bg-[var(--accent)]" />
                复盘不是一个分数
              </p>
              <h2 className="mt-3 text-balance text-2xl font-semibold">知道哪里没讲清，也知道该怎么补</h2>
              <p className="mt-3 max-w-[420px] text-[15px] leading-relaxed text-[var(--muted)]">
                每条评价保留回答证据、评分标准和模型版本。没有足够证据时，系统会说明&ldquo;不确定&rdquo;，而不是给你编一个结论。
              </p>
            </div>
            <blockquote className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-6">
              <span className="text-xs font-medium uppercase text-[var(--accent)]">你的回答证据</span>
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
              把 AI 写过的项目，重新变成你能解释、能调试、能取舍的项目。
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

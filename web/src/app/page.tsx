import { ArrowRight, Bot, Check, CheckCircle2, FileSearch, ListChecks, Quote, SearchCheck, ShieldCheck, Target } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { currentUser } from "@/lib/auth-server";

const capabilities = [
  { icon: FileSearch, title: "从你的经历出题", text: "先解析简历与岗位描述，再让你确认系统理解得是否正确。" },
  { icon: Target, title: "追问具体，而非背题", text: "围绕项目选择、故障处理和技术取舍继续深挖。" },
  { icon: Quote, title: "评价可以回到证据", text: "复盘引用你的原回答，区分能力不足、证据不足与未考察。" },
];

export default async function Home({ searchParams }: { searchParams: Promise<{ account?: string }> }) {
  const accountDeleted = (await searchParams).account === "deleted";
  const user = await currentUser();
  return (
    <div className="landing-page">
      {accountDeleted && <div className="landing-notice" role="status"><CheckCircle2 size={16} /><span>账号及关联数据已永久删除</span></div>}
      <header className="landing-header">
        <Link href="/" className="brand-link" aria-label="InterviewCopilot 首页"><span className="brand-mark">面</span><span><span className="brand-name">InterviewCopilot</span><span className="brand-subtitle">面壁 · 技术面试训练</span></span></Link>
        <nav aria-label="首页导航"><a href="#how-it-works">如何工作</a><a href="#evidence">证据化复盘</a></nav>
        <div className="landing-auth">{user ? <><Link href="/account" className="landing-login">{user.username}</Link><Link href="/training" className="primary-cta">今日训练 <ArrowRight size={15} /></Link></> : <><Link href="/login" className="landing-login">登录</Link><Link href="/register" className="primary-cta">免费开始 <ArrowRight size={15} /></Link></>}</div>
      </header>

      <main>
        <section className="landing-hero">
          <div className="landing-hero-copy">
            <p className="setup-kicker"><span />针对真实经历的技术面试训练</p>
            <h1>不是再做一套题，<br />而是练会<span>讲清你的项目</span></h1>
            <p>上传简历和目标岗位，先校正 AI 对你的理解，再进入一场接近真实视频会议节奏的模拟技术面试。</p>
            <div className="landing-hero-actions">{user ? <><Link href="/training" className="landing-primary">查看今日教练建议 <ArrowRight size={17} /></Link><Link href="/history" className="secondary-button">回看成长档案</Link></> : <><Link href="/register" className="landing-primary">创建训练账号 <ArrowRight size={17} /></Link><Link href="/login" className="secondary-button">已有账号，登录</Link></>}</div>
            <div className="landing-trust"><span><ShieldCheck size={14} />材料默认保留 7 天</span><span><CheckCircle2 size={14} />评价附带回答证据</span></div>
          </div>
          <div className="landing-product-shot">
            <div className="product-shot-bar"><span><i />模拟面试进行中</span><small>真实产品界面</small></div>
            <Image src="/interview-room-preview.png" alt="InterviewCopilot 模拟视频面试室界面" width={1280} height={800} priority />
            <aside className="landing-agent-trace" aria-label="AI 面试教练工作轨迹示意">
              <header><Bot size={17} /><div><span>AI 工作轨迹</span><strong>正在形成追问策略</strong></div><small>LIVE</small></header>
              <ol>
                <li className="done"><Check size={13} /><span>读取简历与 JD</span><small>完成</small></li>
                <li className="active"><SearchCheck size={13} /><span>匹配回答证据</span><small>进行中</small></li>
                <li><ListChecks size={13} /><span>更新追问计划</span><small>下一步</small></li>
              </ol>
            </aside>
          </div>
        </section>

        <section className="landing-capabilities" id="how-it-works">
          <div className="landing-section-heading"><p>训练链路</p><h2>从材料到复盘，每一步都让你确认</h2></div>
          <div className="capability-grid">{capabilities.map(({ icon: Icon, title, text }, index) => <article key={title}><span>0{index + 1}</span><Icon size={20} /><h3>{title}</h3><p>{text}</p></article>)}</div>
        </section>

        <section className="landing-evidence" id="evidence">
          <div><p className="setup-kicker"><span />复盘不是一个分数</p><h2>知道哪里没讲清，也知道该怎么补</h2><p>每条评价保留回答证据、评分标准和模型版本。没有足够证据时，系统会说明“不确定”，而不是给你编一个结论。</p></div>
          <blockquote><span>你的回答证据</span>“我用 LangGraph 重构了流程，因为原来的 Chain 难以恢复中断状态……”<footer>改进方向：补充状态持久化方案，以及为什么没有选择普通任务队列。</footer></blockquote>
        </section>
      </main>

      <footer className="landing-footer"><span>InterviewCopilot · 面壁</span><p>把 AI 写过的项目，重新变成你能解释、能调试、能取舍的项目。</p><Link href={user ? "/setup" : "/register"}>{user ? "开始新训练" : "开始第一次训练"} <ArrowRight size={14} /></Link></footer>
    </div>
  );
}

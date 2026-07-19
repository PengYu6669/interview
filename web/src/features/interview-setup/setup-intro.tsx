import { ShieldCheck } from "lucide-react";

export function SetupIntro() {
  return (
    <section className="setup-briefing" aria-labelledby="setup-title">
      <div className="setup-briefing-copy">
        <p className="setup-kicker"><span />新建模拟面试</p>
        <h1 id="setup-title">把你的真实经历，变成一场有针对性的技术面试</h1>
        <span className="privacy-note"><ShieldCheck size={15} />不保存原文件；登录后提取文本与训练草稿保留 7 天，可随时删除</span>
      </div>
    </section>
  );
}

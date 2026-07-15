import { FileSearch, ListChecks, ShieldCheck, Video } from "lucide-react";

import { DocumentParseStatus } from "./model";

const steps = [
  { index: "01", title: "读取材料", description: "校验并提取原文", icon: FileSearch },
  { index: "02", title: "确认理解", description: "核对技能与证据", icon: ListChecks },
  { index: "03", title: "进入面试", description: "先确认面试蓝图", icon: Video },
];

export function SetupIntro({ parseStatus }: { parseStatus: DocumentParseStatus }) {
  const activeIndex = parseStatus === "success" ? 1 : 0;

  return (
    <section className="setup-briefing" aria-labelledby="setup-title">
      <div className="setup-briefing-copy">
        <p className="setup-kicker"><span />新建模拟面试</p>
        <h1 id="setup-title">把你的真实经历，变成一场有针对性的技术面试</h1>
        <p>提供简历和目标岗位。系统先让你确认它理解得是否正确，再决定问什么，不会直接拿一套通用题开始。</p>
        <span className="privacy-note"><ShieldCheck size={15} />材料当前只保存在本次浏览器会话中</span>
      </div>

      <ol className="setup-flow" aria-label="创建面试流程">
        {steps.map((step, index) => {
          const Icon = step.icon;
          const state = index < activeIndex ? "done" : index === activeIndex ? "active" : "pending";
          return (
            <li className={`setup-flow-step setup-flow-${state}`} key={step.index}>
              <span className="setup-flow-icon"><Icon size={17} /></span>
              <div><small>{step.index}</small><strong>{step.title}</strong><p>{step.description}</p></div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

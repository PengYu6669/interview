import { Check, FileSearch, ListChecks, Video } from "lucide-react";
import Link from "next/link";

const steps = [
  { label: "准备材料", href: "/setup", icon: FileSearch },
  { label: "校正理解", href: "/review", icon: ListChecks },
  { label: "确认蓝图", href: "/blueprint", icon: Video },
];

export function InterviewFlowProgress({ current }: { current: 1 | 2 | 3 }) {
  return <nav className="interview-flow-progress" aria-label="新建面试进度">
    {steps.map((step, index) => {
      const number = index + 1;
      const completed = number < current;
      const active = number === current;
      const Icon = step.icon;
      const content = <><span>{completed ? <Check size={13} /> : <Icon size={14} />}</span><div><small>步骤 {number}</small><strong>{step.label}</strong></div></>;
      return completed
        ? <Link href={step.href} className="completed" key={step.href}>{content}</Link>
        : <div className={active ? "active" : "pending"} aria-current={active ? "step" : undefined} key={step.href}>{content}</div>;
    })}
  </nav>;
}

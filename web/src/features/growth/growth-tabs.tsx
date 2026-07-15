import { BarChart3, CalendarCheck2, History } from "lucide-react";
import Link from "next/link";

export type GrowthView = "records" | "capabilities" | "plan";

const tabs: Array<{ view: GrowthView; label: string; icon: typeof History }> = [
  { view: "records", label: "训练记录", icon: History },
  { view: "capabilities", label: "能力画像", icon: BarChart3 },
  { view: "plan", label: "求职计划", icon: CalendarCheck2 },
];

export function GrowthTabs({ active }: { active: GrowthView }) {
  return <nav className="growth-tabs" aria-label="成长档案视图">{tabs.map((tab) => {
    const Icon = tab.icon;
    return <Link key={tab.view} className={active === tab.view ? "active" : ""} aria-current={active === tab.view ? "page" : undefined} href={`/history?view=${tab.view}`}><Icon size={15} />{tab.label}</Link>;
  })}</nav>;
}

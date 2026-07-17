import { BarChart3, CalendarCheck2, History } from "lucide-react";
import { SegmentedNav } from "@/components/ui/segmented-nav";

export type GrowthView = "records" | "capabilities" | "plan";

const tabs: Array<{ view: GrowthView; label: string; icon: typeof History }> = [
  { view: "records", label: "训练记录", icon: History },
  { view: "capabilities", label: "能力画像", icon: BarChart3 },
  { view: "plan", label: "求职计划", icon: CalendarCheck2 },
];

export function GrowthTabs({ active }: { active: GrowthView }) {
  return <SegmentedNav className="growth-view-tabs" active={active} label="成长档案视图" items={tabs.map((tab) => ({ value: tab.view, label: tab.label, icon: tab.icon, href: `/history?view=${tab.view}` }))} />;
}

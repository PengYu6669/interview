import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PageIntro, PageShell } from "@/components/page-shell";
import { Button } from "@/components/ui/button";
import { InterviewHistory } from "@/features/history/interview-history";
import { AbilityProfile } from "@/features/profile/ability-profile";
import { CareerPlanner } from "@/features/growth/career-planner";
import { GrowthTabs, type GrowthView } from "@/features/growth/growth-tabs";
import { requirePageUser } from "@/lib/page-auth";

export default async function HistoryPage({ searchParams }: { searchParams: Promise<{ view?: string }> }) {
  const requested = (await searchParams).view;
  if (requested === "profile") redirect("/history?view=capabilities");
  const view: GrowthView = requested === "capabilities" || requested === "plan" ? requested : "records";
  await requirePageUser("/history");
  return <PageShell active="history">
    <div className="content-container growth-nav-container"><GrowthTabs active={view} /></div>
    {view === "capabilities" ? <AbilityProfile /> : <main className="content-container history-page">
      <PageIntro title={view === "plan" ? "求职计划" : "训练记录"} actions={view === "records" ? <Button asChild><Link href="/setup">开始新训练 <ArrowRight size={16} /></Link></Button> : undefined} />
      {view === "plan" ? <CareerPlanner /> : <InterviewHistory />}
    </main>}
  </PageShell>;
}

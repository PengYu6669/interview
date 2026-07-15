import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { PageIntro, PageShell } from "@/components/page-shell";
import { InterviewHistory } from "@/features/history/interview-history";
import { requirePageUser } from "@/lib/page-auth";

export default async function HistoryPage({ searchParams }: { searchParams: Promise<{ view?: string }> }) {
  if ((await searchParams).view === "profile") redirect("/profile");
  await requirePageUser("/history");
  return <PageShell active="history"><main className="content-container history-page">
    <PageIntro eyebrow="训练记录" title="每一次训练，都应该留下可复查的证据" description="按时间回看面试题目、回答证据、评分版本和改进建议。" actions={<Link href="/setup" className="primary-cta">开始新训练 <ArrowRight size={16} /></Link>} />
    <InterviewHistory />
  </main></PageShell>;
}

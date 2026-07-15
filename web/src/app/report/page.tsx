import { PageShell } from "@/components/page-shell";
import { InterviewReport } from "@/features/report/interview-report";
import { requirePageUser } from "@/lib/page-auth";

export default async function ReportPage({ searchParams }: { searchParams: Promise<{ session?: string }> }) {
  const sessionId = (await searchParams).session ?? "";
  await requirePageUser(sessionId ? `/report?session=${encodeURIComponent(sessionId)}` : "/report");
  return <PageShell active="history"><InterviewReport sessionId={sessionId} /></PageShell>;
}

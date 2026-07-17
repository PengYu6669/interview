import { PageShell } from "@/components/page-shell";
import { QuestionWorkspace } from "@/features/questions/question-workspace";

export default async function QuestionPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<{ plan?: string; planItem?: string }> }) {
  const query = await searchParams;
  const planId = /^[0-9a-f-]{36}$/i.test(query.plan ?? "") ? query.plan : undefined;
  const planItemId = /^[0-9a-f-]{36}$/i.test(query.planItem ?? "") ? query.planItem : undefined;
  return <PageShell active="questions"><QuestionWorkspace slug={(await params).slug} planId={planId} planItemId={planItemId} /></PageShell>;
}

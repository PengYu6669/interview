import { PageShell } from "@/components/page-shell";
import { QuestionWorkspace } from "@/features/questions/question-workspace";

export default async function QuestionPage({ params }: { params: Promise<{ slug: string }> }) {
  return <PageShell active="questions"><QuestionWorkspace slug={(await params).slug} /></PageShell>;
}

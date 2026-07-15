import { PageShell } from "@/components/page-shell";
import { QuestionBank } from "@/features/questions/question-bank";

export default function QuestionsPage() {
  return <PageShell active="questions"><QuestionBank /></PageShell>;
}

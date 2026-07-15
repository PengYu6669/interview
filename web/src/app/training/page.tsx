import { PageShell } from "@/components/page-shell";
import { TrainingHub } from "@/features/training/training-hub";
import { requirePageUser } from "@/lib/page-auth";

export default async function TrainingPage() {
  await requirePageUser("/training");
  return <PageShell active="training"><TrainingHub /></PageShell>;
}

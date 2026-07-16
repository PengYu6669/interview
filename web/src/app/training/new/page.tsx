import { redirect } from "next/navigation";

import { PageShell } from "@/components/page-shell";
import { CoachingSetup } from "@/features/training/coaching-setup";
import { CoachingDifficulty, CoachingMode } from "@/lib/coaching";
import { requirePageUser } from "@/lib/page-auth";

export default async function NewCoachingPage({ searchParams }: { searchParams: Promise<{ mode?: string; focus?: string; difficulty?: string; planItem?: string }> }) {
  await requirePageUser("/training/new");
  const params = await searchParams;
  const mode = params.mode;
  if (mode !== "structured_expression" && mode !== "business_sense") redirect("/training");
  const difficulty = (["guided", "assisted", "pressure"] as const).includes(params.difficulty as CoachingDifficulty) ? params.difficulty as CoachingDifficulty : "guided";
  const planItemId = /^[0-9a-f-]{36}$/i.test(params.planItem ?? "") ? params.planItem : undefined;
  return <PageShell active="training"><CoachingSetup mode={mode as CoachingMode} initialFocus={params.focus?.slice(0, 500) ?? ""} initialDifficulty={difficulty} planItemId={planItemId} /></PageShell>;
}

import { redirect } from "next/navigation";

import { PageShell } from "@/components/page-shell";
import { CoachingSetup } from "@/features/training/coaching-setup";
import { CoachingMode } from "@/lib/coaching";
import { requirePageUser } from "@/lib/page-auth";

export default async function NewCoachingPage({ searchParams }: { searchParams: Promise<{ mode?: string }> }) {
  await requirePageUser("/training/new");
  const mode = (await searchParams).mode;
  if (mode !== "structured_expression" && mode !== "business_sense") redirect("/training");
  return <PageShell active="training"><CoachingSetup mode={mode as CoachingMode} /></PageShell>;
}

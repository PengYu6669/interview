import { InterviewSetup } from "@/features/interview-setup/interview-setup";

export default async function SetupPage({ searchParams }: { searchParams: Promise<{ planItem?: string }> }) {
  const { planItem } = await searchParams;
  const careerPlanItemId = /^[0-9a-f-]{36}$/i.test(planItem ?? "") ? planItem : undefined;
  return <InterviewSetup careerPlanItemId={careerPlanItemId} />;
}

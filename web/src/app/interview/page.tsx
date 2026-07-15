import { InterviewRoom } from "@/features/interview-room/interview-room";
import { requirePageUser } from "@/lib/page-auth";

export default async function InterviewPage({ searchParams }: { searchParams: Promise<{ session?: string }> }) {
  const sessionId = (await searchParams).session ?? "";
  await requirePageUser(sessionId ? `/interview?session=${encodeURIComponent(sessionId)}` : "/interview");
  return <InterviewRoom sessionId={sessionId} />;
}

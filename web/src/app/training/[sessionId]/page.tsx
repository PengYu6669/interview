import { PageShell } from "@/components/page-shell";
import { CoachingRoom } from "@/features/training/coaching-room";
import { requirePageUser } from "@/lib/page-auth";

export default async function CoachingSessionPage({ params }: PageProps<"/training/[sessionId]">) {
  const { sessionId } = await params;
  await requirePageUser(`/training/${sessionId}`);
  return <PageShell active="training"><CoachingRoom sessionId={sessionId} /></PageShell>;
}

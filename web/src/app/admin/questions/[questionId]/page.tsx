import { notFound, redirect } from "next/navigation";
import { z } from "zod";

import { AdminQuestionEditor } from "@/features/admin/admin-question-editor";
import { currentUser } from "@/lib/auth-server";

const idSchema = z.string().uuid();

export default async function AdminQuestionPage({ params }: PageProps<"/admin/questions/[questionId]">) {
  const user = await currentUser();
  if (!user) redirect("/login?next=/admin/questions");
  if (user.role !== "admin") notFound();
  const { questionId } = await params;
  if (!idSchema.safeParse(questionId).success) notFound();
  return <AdminQuestionEditor questionId={questionId} />;
}

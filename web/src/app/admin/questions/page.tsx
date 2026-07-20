import { notFound, redirect } from "next/navigation";

import { AdminQuestionManager } from "@/features/admin/admin-question-manager";
import { currentUser } from "@/lib/auth-server";

export default async function AdminQuestionsPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=/admin/questions");
  if (user.role !== "admin") notFound();
  return <AdminQuestionManager />;
}

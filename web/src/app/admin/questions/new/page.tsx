import { notFound, redirect } from "next/navigation";

import { AdminQuestionEditor } from "@/features/admin/admin-question-editor";
import { currentUser } from "@/lib/auth-server";

export default async function NewAdminQuestionPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=/admin/questions/new");
  if (user.role !== "admin") notFound();
  return <AdminQuestionEditor questionId="new" />;
}

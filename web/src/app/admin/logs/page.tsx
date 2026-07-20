import { notFound, redirect } from "next/navigation";

import { AdminLogViewer } from "@/features/admin/admin-log-viewer";
import { currentUser } from "@/lib/auth-server";

export default async function AdminLogsPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=/admin/logs");
  if (user.role !== "admin") notFound();
  return <AdminLogViewer />;
}

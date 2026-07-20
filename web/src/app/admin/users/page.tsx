import { notFound, redirect } from "next/navigation";

import { AdminUserManager } from "@/features/admin/admin-user-manager";
import { currentUser } from "@/lib/auth-server";

export default async function AdminUsersPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=/admin/users");
  if (user.role !== "admin") notFound();
  return <AdminUserManager />;
}

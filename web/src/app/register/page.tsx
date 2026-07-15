import { AuthPage } from "@/components/auth-page";
import { currentUser, safeInternalPath } from "@/lib/auth-server";
import { redirect } from "next/navigation";

export default async function RegisterPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const requested = (await searchParams).next;
  const nextPath = safeInternalPath(requested);
  if (await currentUser()) redirect(nextPath);
  return <AuthPage mode="register" nextPath={nextPath} />;
}

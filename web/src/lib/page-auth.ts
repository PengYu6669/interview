import "server-only";

import { redirect } from "next/navigation";

import { currentUser, safeInternalPath } from "./auth-server";

export async function requirePageUser(nextPath: string): Promise<void> {
  if (await currentUser()) return;
  const safeNext = safeInternalPath(nextPath);
  redirect(`/login?next=${encodeURIComponent(safeNext)}`);
}

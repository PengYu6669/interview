import { PageShell } from "@/components/page-shell";
import { AccountCenter } from "@/features/account/account-center";
import { requirePageUser } from "@/lib/page-auth";

export default async function AccountPage() {
  await requirePageUser("/account");
  return <PageShell active="account"><AccountCenter /></PageShell>;
}

import { PageShell } from "@/components/page-shell";
import { AbilityProfile } from "@/features/profile/ability-profile";
import { requirePageUser } from "@/lib/page-auth";

export default async function ProfilePage() {
  await requirePageUser("/profile");
  return <PageShell active="profile"><AbilityProfile /></PageShell>;
}

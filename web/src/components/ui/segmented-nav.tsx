import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";

export type SegmentedNavItem = {
  href: string;
  label: string;
  value: string;
  icon?: LucideIcon;
};

export function SegmentedNav({ items, active, label, className }: { items: SegmentedNavItem[]; active: string; label: string; className?: string }) {
  return <nav className={cn("inline-flex max-w-full gap-1 overflow-x-auto rounded-lg border border-[var(--line)] bg-[var(--surface-muted)] p-1", className)} aria-label={label}>
    {items.map(({ href, label: itemLabel, value, icon: Icon }) => <Link key={value} href={href} aria-current={active === value ? "page" : undefined} className={cn("inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md px-3 text-xs font-semibold text-[var(--muted)] transition-colors hover:text-[var(--ink)]", active === value && "bg-[var(--surface)] text-[var(--ink)] shadow-sm")}>
      {Icon && <Icon size={14} />}{itemLabel}
    </Link>)}
  </nav>;
}

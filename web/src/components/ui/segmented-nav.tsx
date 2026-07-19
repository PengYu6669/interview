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
  return <nav className={cn("inline-flex max-w-full gap-1 overflow-x-auto rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-1", className)} aria-label={label}>
    {items.map(({ href, label: itemLabel, value, icon: Icon }) => <Link key={value} href={href} aria-current={active === value ? "page" : undefined} className={cn("inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md px-4 text-sm font-medium text-[var(--text-secondary)] transition-colors duration-150 hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]", active === value && "bg-[var(--accent)] !text-white hover:bg-[var(--accent-hover)] hover:!text-white")}>
      {Icon && <Icon size={14} />}{itemLabel}
    </Link>)}
  </nav>;
}

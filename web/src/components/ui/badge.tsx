import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex min-h-6 items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold",
  {
    variants: {
      tone: {
        neutral: "border-[var(--line)] bg-[var(--surface-muted)] text-[var(--muted)]",
        accent: "border-[#abd4cd] bg-[var(--accent-soft)] text-[var(--accent-dark)]",
        success: "border-[#a9d4c2] bg-[#edf8f3] text-[var(--success)]",
        warning: "border-[#e2c99a] bg-[#fff8e9] text-[var(--warning)]",
        danger: "border-[#e3b7b2] bg-[#fff3f1] text-[var(--danger)]",
        outline: "border-[var(--line-strong)] bg-transparent text-[var(--ink)]",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export function Badge({ className, tone, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

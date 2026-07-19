import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex min-h-6 items-center gap-1 rounded-full border px-3 py-1 text-xs font-medium",
  {
    variants: {
      tone: {
        neutral: "border-[var(--border-default)] bg-[var(--bg-hover)] text-[var(--text-secondary)]",
        accent: "border-[var(--accent-light)] bg-[var(--accent-light)] text-[var(--accent)]",
        success: "border-[var(--success-bg)] bg-[var(--success-bg)] text-[var(--success)]",
        warning: "border-[var(--warning-bg)] bg-[var(--warning-bg)] text-[var(--warning)]",
        danger: "border-[var(--danger-border)] bg-[var(--danger-bg)] text-[var(--danger)]",
        outline: "border-[var(--border-hover)] bg-transparent text-[var(--text-primary)]",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export function Badge({ className, tone, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

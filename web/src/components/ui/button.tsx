import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-lg font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-light)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-canvas)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "border border-[var(--accent)] bg-[var(--accent)] !text-white hover:border-[var(--accent-hover)] hover:bg-[var(--accent-hover)] hover:!text-white",
        secondary: "border border-[var(--border-default)] bg-transparent text-[var(--text-primary)] hover:border-[var(--border-hover)] hover:bg-[var(--bg-hover)]",
        ghost: "border border-transparent bg-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]",
        subtle: "border border-transparent bg-[var(--accent-light)] text-[var(--accent)] hover:bg-[var(--bg-hover)]",
        danger: "border border-[var(--danger-border)] bg-[var(--danger-bg)] text-[var(--danger)] hover:border-[var(--danger)] hover:bg-[var(--danger)] hover:text-white",
        link: "h-auto border-0 bg-transparent p-0 text-[var(--accent-dark)] underline-offset-4 hover:underline",
        onDark: "border border-[var(--bg-surface)] bg-[var(--bg-surface)] !text-[var(--accent)] hover:bg-[var(--bg-subtle)] hover:!text-[var(--accent-hover)]",
        linkOnDark: "h-auto border-0 bg-transparent p-0 !text-white underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4 text-[13px]",
        lg: "h-11 px-5 text-sm",
        icon: "size-9 p-0",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Component = asChild ? Slot : "button";
  return <Component className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}

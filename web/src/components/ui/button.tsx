import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-md font-semibold transition-[background-color,color,border-color,box-shadow,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--canvas)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "border border-[var(--ink)] bg-[var(--ink)] text-white! shadow-sm hover:bg-[#283330] hover:text-white! active:translate-y-px",
        secondary: "border border-[var(--line-strong)] bg-[var(--surface)] text-[var(--ink)] shadow-sm hover:border-[#aab6b2] hover:bg-[var(--surface-muted)]",
        ghost: "border border-transparent bg-transparent text-[var(--muted)] hover:bg-[var(--soft)] hover:text-[var(--ink)]",
        subtle: "border border-transparent bg-[var(--accent-soft)] text-[var(--accent-dark)] hover:bg-[#d7efeb]",
        danger: "border border-[#d7aaa5] bg-[#fff5f3] text-[var(--danger)] hover:bg-[#ffebe8]",
        link: "h-auto border-0 bg-transparent p-0 text-[var(--accent-dark)] underline-offset-4 hover:underline",
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

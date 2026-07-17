import { cn } from "@/lib/cn";

export type SegmentedControlOption<T extends string> = {
  value: T;
  label: string;
  count?: number;
};

export function SegmentedControl<T extends string>({
  options,
  value,
  onValueChange,
  label,
  className,
}: {
  options: Array<SegmentedControlOption<T>>;
  value: T;
  onValueChange: (value: T) => void;
  label: string;
  className?: string;
}) {
  return <div className={cn("inline-flex max-w-full gap-1 overflow-x-auto rounded-lg border border-[var(--line)] bg-[var(--surface-muted)] p-1", className)} role="group" aria-label={label}>
    {options.map((option) => {
      const active = option.value === value;
      return <button key={option.value} type="button" aria-pressed={active} onClick={() => onValueChange(option.value)} className={cn("inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md border-0 px-3 text-xs font-semibold text-[var(--muted)] transition-colors hover:text-[var(--ink)]", active && "bg-[var(--surface)] text-[var(--ink)] shadow-sm")}>
        {option.label}
        {option.count !== undefined && <span className={cn("grid min-w-4 place-items-center rounded bg-[#dfe5e3] px-1 text-[10px] tabular-nums", active && "bg-[var(--accent-soft)] text-[var(--accent-dark)]")}>{option.count}</span>}
      </button>;
    })}
  </div>;
}

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
  return <div className={cn("inline-flex max-w-full gap-1 overflow-x-auto rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-1", className)} role="group" aria-label={label}>
    {options.map((option) => {
      const active = option.value === value;
      return <button key={option.value} type="button" aria-pressed={active} onClick={() => onValueChange(option.value)} className={cn("inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md border-0 px-4 text-sm font-medium text-[var(--text-secondary)] transition-colors duration-150 hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]", active && "bg-[var(--accent)] !text-white hover:bg-[var(--accent-hover)] hover:!text-white")}>
        {option.label}
        {option.count !== undefined && <span className={cn("grid min-w-5 place-items-center rounded-full bg-[var(--bg-hover)] px-1 text-xs tabular-nums", active && "bg-white/15 !text-white")}>{option.count}</span>}
      </button>;
    })}
  </div>;
}

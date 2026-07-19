export function TextSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="grid gap-2.5" aria-hidden>
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="h-3.5 animate-pulse rounded bg-[var(--surface-muted)]"
          style={{ width: index === lines - 1 ? "60%" : "100%" }}
        />
      ))}
    </div>
  );
}

export function CardSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid gap-2.5" aria-label="正在加载">
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="rounded-[0.9rem] border border-[var(--line)] bg-[var(--surface)] p-4 animate-pulse"
        >
          <div className="mb-2 h-3.5 w-2/5 rounded bg-[var(--surface-muted)]" />
          <div className="h-3 w-4/5 rounded bg-[var(--surface-muted)]" />
        </div>
      ))}
    </div>
  );
}

export function PageSkeleton() {
  return (
    <main className="mx-auto w-[min(72rem,calc(100%-3rem))] pb-20 pt-12">
      <div className="mb-6 h-7 w-72 animate-pulse rounded bg-[var(--surface-muted)]" />
      <div className="mb-2 h-10 w-96 animate-pulse rounded bg-[var(--surface-muted)]" />
      <div className="mb-8 h-5 w-[32rem] animate-pulse rounded bg-[var(--surface-muted)]" />
      <CardSkeleton count={3} />
    </main>
  );
}

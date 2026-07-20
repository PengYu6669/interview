import { TrendLine } from "@/components/data-visualization";

export type AbilityKlinePoint = {
  session_id: string;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  evidence_coverage: number;
  confidence: number;
};

export function AbilityKline({ points }: { points: AbilityKlinePoint[] }) {
  if (!points.length) return <div className="grid min-h-36 place-content-center text-center" role="status"><strong className="text-sm">暂无训练表现记录</strong></div>;

  return <><TrendLine points={points.map((point) => ({ label: point.date, value: point.close, confidence: point.confidence }))} /><div className="mt-4 grid gap-2 sm:grid-cols-2">{points.slice(-4).reverse().map((point) => <a className="flex items-center justify-between gap-4 rounded-md bg-[var(--bg-subtle)] px-3 py-2.5 text-sm transition-colors hover:bg-[var(--bg-hover)]" key={point.session_id} href={`/report?session=${point.session_id}`} aria-label={`${point.date}，当场表现 ${point.close} 分，查看对应报告`}>
    <span><time className="text-xs text-[var(--muted)]">{point.date}</time><strong className="ml-3">{point.close} 分</strong></span><small className="text-xs text-[var(--muted)]">稳定度 {Math.round(point.confidence * 100)}%</small>
  </a>)}</div></>;
}

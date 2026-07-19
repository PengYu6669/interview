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
  if (!points.length) return <div className="grid min-h-36 place-content-center gap-1 text-center" role="status"><strong className="text-sm">暂无训练表现记录</strong><span className="text-xs text-[var(--muted)]">完成模拟面试并生成证据报告后出现</span></div>;

  return <><TrendLine points={points.map((point) => ({ label: point.date, value: point.close, confidence: point.confidence }))} /><div className="mt-4 divide-y divide-[var(--line)] border-y border-[var(--line)]">{points.map((point) => <a className="grid grid-cols-[70px_48px_minmax(0,1fr)] items-center gap-3 py-3 text-sm hover:bg-[var(--bg-subtle)]" key={point.session_id} href={`/report?session=${point.session_id}`} aria-label={`${point.date}，当场表现 ${point.close} 分，查看对应报告`}>
    <time className="text-xs text-[var(--muted)]">{point.date}</time><strong>{point.close}</strong><small className="text-right text-xs text-[var(--muted)]">覆盖 {point.evidence_coverage}% · 稳定度 {Math.round(point.confidence * 100)}%</small>
  </a>)}</div></>;
}
import { TrendLine } from "@/components/data-visualization";

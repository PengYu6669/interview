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
  if (!points.length) return <div className="kline-empty" role="status"><div className="kline-empty-grid"><i /><i /><i /><i /></div><strong>暂无训练表现记录</strong><span>完成模拟面试并生成证据报告后出现</span></div>;

  return <div className="ability-session-list">{points.map((point) => <a key={point.session_id} href={`/report?session=${point.session_id}`} aria-label={`${point.date}，当场表现 ${point.close} 分，查看对应报告`}>
    <time>{point.date}</time><strong>{point.close}</strong><span>当场表现</span><small>证据覆盖 {point.evidence_coverage}% · 稳定度 {Math.round(point.confidence * 100)}%</small>
  </a>)}</div>;
}

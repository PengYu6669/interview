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
  if (!points.length) return <div className="kline-empty" role="status"><div className="kline-empty-grid"><i /><i /><i /><i /></div><strong>暂无能力 K 线</strong><span>完成训练后生成</span></div>;

  const width = 720;
  const chartWidth = Math.max(width, points.length * 72);
  const height = 250;
  const top = 18;
  const bottom = 32;
  const chartHeight = height - top - bottom;
  const toY = (score: number) => top + ((100 - score) / 100) * chartHeight;
  const step = chartWidth / points.length;
  const candleWidth = Math.min(20, step * 0.4);

  return <div className="kline-chart"><div className="kline-scroll"><svg viewBox={`0 0 ${chartWidth} ${height}`} style={{ minWidth: `${chartWidth}px` }} role="img" aria-label="能力增长 K 线图">
    {[25, 50, 75, 100].map((score) => <g key={score}><line x1="0" y1={toY(score)} x2={chartWidth} y2={toY(score)} className="kline-grid-line" /><text x="4" y={toY(score) - 5}>{score}</text></g>)}
    {points.map((point, index) => {
      const x = step * index + step / 2;
      const rising = point.close >= point.open;
      const bodyTop = toY(Math.max(point.open, point.close));
      const bodyHeight = Math.max(3, Math.abs(toY(point.open) - toY(point.close)));
      return <a key={point.session_id} href={`/report?session=${point.session_id}`} aria-label={`${point.date}，收盘 ${point.close} 分，查看对应报告`}><g className={rising ? "kline-rise" : "kline-fall"}><title>{`${point.date}：开 ${point.open}，高 ${point.high}，低 ${point.low}，收 ${point.close}，证据覆盖 ${point.evidence_coverage}%`}</title><line x1={x} y1={toY(point.high)} x2={x} y2={toY(point.low)} /><rect x={x - candleWidth / 2} y={bodyTop} width={candleWidth} height={bodyHeight} opacity={Math.max(.35, point.confidence)} /><text className="kline-date" x={x} y={height - 8} textAnchor="middle">{point.date}</text></g></a>;
    })}
  </svg></div><div className="kline-legend"><span><i className="rise" />收盘不低于开盘</span><span><i className="fall" />收盘低于开盘</span><span>点击蜡烛查看对应报告</span></div></div>;
}

import { cn } from "@/lib/cn";

export function ScoreRing({ value, label = "表现分", size = 148 }: { value: number; label?: string; size?: number }) {
  const score = Math.max(0, Math.min(100, Math.round(value)));
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  return <div className="score-ring" style={{ width: size, height: size }} role="img" aria-label={`${label} ${score} 分`}>
    <svg viewBox="0 0 128 128" aria-hidden="true">
      <circle className="score-ring-track" cx="64" cy="64" r={radius} />
      <circle className="score-ring-value" cx="64" cy="64" r={radius} strokeDasharray={circumference} strokeDashoffset={circumference * (1 - score / 100)} />
    </svg>
    <div><strong>{score}</strong><span>{label}</span></div>
  </div>;
}

export function ConfidenceBar({ value, compact = false }: { value: number; compact?: boolean }) {
  const percent = Math.max(0, Math.min(100, Math.round(value <= 1 ? value * 100 : value)));
  const tone = percent >= 60 ? "high" : percent >= 30 ? "medium" : "low";
  return <div className={cn("confidence-bar", compact && "compact", tone)} aria-label={`可信度 ${percent}%`}>
    <div><span>可信度</span><strong>{percent}%</strong></div>
    <i><b style={{ width: `${percent}%` }} /></i>
  </div>;
}

export type RadarDatum = { label: string; value: number };

export function RadarChart({ data, title = "能力分布" }: { data: RadarDatum[]; title?: string }) {
  const normalized = data.slice(0, 6).map((item) => ({ ...item, value: Math.max(0, Math.min(100, item.value)) }));
  if (normalized.length < 3) return null;
  const center = 160;
  const radius = 78;
  const angle = (index: number) => -Math.PI / 2 + (Math.PI * 2 * index) / normalized.length;
  const point = (index: number, scale: number) => `${center + Math.cos(angle(index)) * radius * scale},${center + Math.sin(angle(index)) * radius * scale}`;
  const levels = [0.25, 0.5, 0.75, 1];
  const polygon = normalized.map((item, index) => point(index, item.value / 100)).join(" ");
  return <div className="radar-chart" role="img" aria-label={`${title}：${normalized.map((item) => `${item.label} ${item.value}分`).join("，")}`}>
    <svg viewBox="0 0 320 320" aria-hidden="true">
      {levels.map((level) => <polygon className="radar-grid" key={level} points={normalized.map((_, index) => point(index, level)).join(" ")} />)}
      {normalized.map((_, index) => <line className="radar-axis" key={index} x1={center} y1={center} x2={point(index, 1).split(",")[0]} y2={point(index, 1).split(",")[1]} />)}
      <polygon className="radar-area" points={polygon} />
      {normalized.map((item, index) => {
        const labelRadius = radius + 42;
        const x = center + Math.cos(angle(index)) * labelRadius;
        const y = center + Math.sin(angle(index)) * labelRadius;
        return <g key={item.label}><circle className="radar-point" cx={point(index, item.value / 100).split(",")[0]} cy={point(index, item.value / 100).split(",")[1]} r="3" /><text x={x} y={y} textAnchor={x < center - 8 ? "end" : x > center + 8 ? "start" : "middle"} dominantBaseline="middle">{item.label}</text></g>;
      })}
    </svg>
  </div>;
}

export function TrendLine({ points }: { points: { label: string; value: number; confidence?: number }[] }) {
  if (!points.length) return null;
  const width = 520;
  const height = 180;
  const padding = { x: 30, y: 24 };
  const chartWidth = width - padding.x * 2;
  const chartHeight = height - padding.y * 2;
  const x = (index: number) => padding.x + (points.length === 1 ? chartWidth / 2 : chartWidth * index / (points.length - 1));
  const y = (value: number) => padding.y + chartHeight * (1 - Math.max(0, Math.min(100, value)) / 100);
  const line = points.map((item, index) => `${x(index)},${y(item.value)}`).join(" ");
  const area = `${padding.x},${height - padding.y} ${line} ${x(points.length - 1)},${height - padding.y}`;
  return <div className="trend-line" role="img" aria-label={points.map((item) => `${item.label} ${item.value}分`).join("，")}>
    <svg viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <defs><linearGradient id="trend-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".25" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></linearGradient></defs>
      {[25, 50, 75].map((value) => <line className="trend-grid" key={value} x1={padding.x} y1={y(value)} x2={width - padding.x} y2={y(value)} />)}
      <polygon className="trend-area" points={area} />
      <polyline className="trend-path" points={line} />
      {points.map((item, index) => <g key={`${item.label}-${index}`} className={item.confidence !== undefined && item.confidence < .4 ? "uncertain" : ""}><circle cx={x(index)} cy={y(item.value)} r="5" /><text x={x(index)} y={y(item.value) - 12} textAnchor="middle">{item.value}</text><text className="trend-label" x={x(index)} y={height - 4} textAnchor="middle">{item.label}</text></g>)}
    </svg>
  </div>;
}

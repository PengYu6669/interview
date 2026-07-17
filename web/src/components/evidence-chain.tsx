import { ArrowDown, Quote, ShieldCheck, Target } from "lucide-react";
import type { ReactNode } from "react";

export function EvidenceChain({
  conclusion,
  evidence,
  previousEvidence,
  basis,
  confidence,
  action,
  meta,
  controls,
  tone = "neutral",
}: {
  conclusion: string;
  evidence?: string | null;
  previousEvidence?: string | null;
  basis: string;
  confidence?: number | null;
  action?: string | null;
  meta?: string;
  controls?: ReactNode;
  tone?: "positive" | "warning" | "neutral";
}) {
  const confidenceLabel = confidence === null || confidence === undefined
    ? "未提供置信度"
    : confidence >= 0.7 ? "证据较稳定" : confidence >= 0.4 ? "初步判断" : "样本不足";
  return <article className={`evidence-chain ${tone}`}>
    <header><div><span>{meta ?? "证据化判断"}</span><h3>{conclusion}</h3></div>{controls}</header>
    <div className="evidence-chain-flow">
      <section><Quote size={15} /><div><strong>{previousEvidence ? "前后回答证据" : "回答证据"}</strong>{previousEvidence && <blockquote><small>来源训练</small>“{previousEvidence}”</blockquote>}<blockquote>{previousEvidence && <small>本次训练</small>}{evidence ? `“${evidence}”` : "当前没有可逐字引用的回答证据"}</blockquote></div></section>
      <ArrowDown className="evidence-chain-arrow" size={14} />
      <section><ShieldCheck size={15} /><div><strong>判断依据</strong><p>{basis}</p><small>{confidenceLabel}{confidence === null || confidence === undefined ? "" : ` · 可信度 ${Math.round(confidence * 100)}%`}</small></div></section>
      {action && <><ArrowDown className="evidence-chain-arrow" size={14} /><section><Target size={15} /><div><strong>下一次验证</strong><p>{action}</p></div></section></>}
    </div>
  </article>;
}

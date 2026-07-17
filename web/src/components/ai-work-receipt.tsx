import { Check, Clock3, LoaderCircle, ShieldCheck } from "lucide-react";

export type AiWorkStep = {
  label: string;
  detail?: string;
};

export function AiWorkReceipt({
  title,
  description,
  steps,
  activeStep,
  status = "running",
  footer,
}: {
  title: string;
  description: string;
  steps: AiWorkStep[];
  activeStep: number;
  status?: "running" | "completed" | "failed";
  footer?: string;
}) {
  return <section className={`ai-work-receipt ${status}`} aria-live="polite">
    <header>
      <span className="ai-work-icon">{status === "running" ? <LoaderCircle className="spin" size={18} /> : <ShieldCheck size={18} />}</span>
      <div><span>AI 工作回执</span><h2>{title}</h2><p>{description}</p></div>
    </header>
    <ol>{steps.map((step, index) => {
      const state = status === "completed" || index < activeStep ? "done" : index === activeStep ? "active" : "pending";
      return <li className={state} key={step.label}>
        <span>{state === "done" ? <Check size={13} /> : state === "active" ? <LoaderCircle className="spin" size={13} /> : index + 1}</span>
        <div><strong>{step.label}</strong>{step.detail && <small>{step.detail}</small>}</div>
      </li>;
    })}</ol>
    {footer && <footer><Clock3 size={13} />{footer}</footer>}
  </section>;
}

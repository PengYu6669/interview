import { SiteHeader } from "./site-header";
import type { ActivePage } from "./site-header";
import { Badge } from "./ui/badge";

export function PageShell({
  active,
  children,
}: {
  active: ActivePage;
  children: React.ReactNode;
}) {
  return (
    <div className="app-canvas">
      <SiteHeader active={active} />
      {children}
    </div>
  );
}

export function PageIntro({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-intro">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function StatusBadge({ tone = "neutral", children }: { tone?: "neutral" | "success" | "warning" | "danger"; children: React.ReactNode }) {
  return <Badge tone={tone}>{children}</Badge>;
}

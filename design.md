# InterviewCopilot · Locked Design System

> Hallmark must preserve this system. Do not pick a catalog theme.
> Scope: training hub presentation only unless the user expands scope.

## Brand

- Product: InterviewCopilot / 面壁 — AI interview coach with evidence-based review
- Voice: calm coach, first-person notes, no invented metrics
- Genre: modern-minimal + paper editorial (not dashboard admin)

## Tokens (locked — do not replace)

Source of truth: `web/src/app/globals.css` `:root`

| Role | Token | Notes |
| --- | --- | --- |
| Canvas | `--paper` / `--canvas` | Warm paper ground |
| Ink | `--ink` / `--ink-soft` | Body and muted text |
| Accent | `--pine` / `--pine-deep` / `--pine-bright` | Primary brand green |
| Gold | `--gold` | Soft emphasis, not CTA spam |
| Danger | `--vermilion` | Errors only |
| Dark room | `--room` / `--room-glow` | Interview room + single ink card only |
| Surface | `--surface` / `--surface-muted` | Cards on paper |
| Line | `--line` / `--line-strong` | Hairlines |
| Shadow | `--shadow-soft` / `--shadow-lift` | Layered, not heavy |
| Radius | prefer `1rem`+ on hero cards | Avoid tiny 8px admin chips for heroes |

Use tokens via `var(--…)` / Tailwind `var(--token)`. No mid-render hex improvisation except within existing brand family.

## Typography

- Fonts: Geist Sans + Geist Mono only (already loaded). No Google Fonts CDN.
- Headings: roman (no italic headers)
- Numbers: `tabular-nums`
- Min readable UI text: 12px; body preferred ≥13–14px

## Macrostructure for Training Hub

Single protagonist page (not multi-module dashboard):

1. Short coach-voice title
2. ONE ink (dark) lesson card with ONE primary CTA
3. AI process trail (loading / preparing)
4. Session strips (continue last training)
5. Weak secondary: “换一种练法” modes + demo entry

## States (same skeleton)

- **State 0 unconfigured**: Lesson 0 — get to know you (role → materials → confirm understanding)
- **State 1 configured, no history**: baseline interview invitation
- **State 2 has history**: evidence-based today’s recommendation

## Hard rules

- Do not make the full first screen a dark stage; dark only on the lesson card
- Do not change navigation, routes, APIs, or other pages
- Do not invent metrics, testimonials, or fake coverage %
- Motion: breathe / light-up / flow only; ≥3s for breathe; respect `prefers-reduced-motion`
- No new dependencies
- No ChatGPT-style chat shell as the hub

## Framework

- Next.js App Router + React + Tailwind v4 + existing `Button` / `Badge` / `cn`
- Edit in place: primarily `web/src/features/training/training-hub.tsx`
- Minimal additive CSS in `web/src/app/globals.css` for keyframes only

# SuperAds Theme — ADs Growth System

The dashboard, auth flow, and marketing surfaces all read from the SuperAds
theme, dual-mode with semantic CSS variables in `frontend/src/index.css` and
Tailwind aliases in `frontend/tailwind.config.js`.

Source of truth: `design-system-template/themes/superads.xml`
(`lib/theme/themes/superads.ts`).

> **Grounding.** Fonts, accents, gradients and the light/dark structure are
> **extracted** from the real source. Surfaces, radii, spacing, shadows and
> motion timings are **inferred** — the upstream `shared/styles.css` was never
> provided. Treat the surface hexes below as a best estimate and correct them
> if the original stylesheet surfaces.

> **This file has been wrong before.** It described the ink + ember theme long
> after the code had moved to Opal Hotel gold. `frontend/src/index.css` is the
> only authority; this table is a convenience copy.

## Tokens

### Surfaces

| Token                  | Dark                 | Light                | Use              |
| ---------------------- | -------------------- | -------------------- | ---------------- |
| `--background`         | `#0A0E1A` page       | `#F8FAFC`            | Page bg          |
| `--card`               | `#141B2D` surface    | `#FFFFFF`            | Card / panel bg  |
| `--popover`            | `#1C2438` elevated   | `#FFFFFF`            | Overlays         |
| `--surface-tertiary`   | `#1C2438`            | `#F1F5F9` sunken     | Elevated card    |
| `--muted`              | `#1F2937` line       | `#F1F5F9`            | Subtle fills     |
| `--border` / `--input` | `#1F2937` line       | `#E2E8F0`            | Borders          |

### Typography

| Token                     | Dark             | Light            | Use                     |
| ------------------------- | ---------------- | ---------------- | ----------------------- |
| `--foreground`            | `#F8FAFC`        | `#0F172A`        | Primary text            |
| `--muted-foreground`      | `#94A3B8`        | `#64748B`        | Secondary text          |
| Font family `font-sans`   | Inter            | Inter            | Body                    |
| Font family `font-display`| Space Grotesk    | Space Grotesk    | Headings                |
| Font family `font-mono`   | JetBrains Mono   | JetBrains Mono   | Labels, status, tabular |
| `font-sans-arabic`        | Noto Sans Arabic | Noto Sans Arabic | RTL surfaces            |

### Brand & status

| Token                        | Dark               | Light              | Use                                |
| ---------------------------- | ------------------ | ------------------ | ---------------------------------- |
| `--primary`                  | `#3B82F6` blue     | `#3B82F6`          | CTA, accent, focus ring            |
| `--secondary`                | `#60A5FA` hover    | `#2563EB` hover    | Gradient stop, hover               |
| `--accent`                   | `#06B6D4` cyan     | `#06B6D4`          | Multi-series chart, neutral signal |
| `--insight`                  | `#8B5CF6` purple   | `#8B5CF6`          | Insight / secondary series         |
| `--success`                  | `#10B981`          | `#10B981`          | Healthy / pass                     |
| `--warning`                  | `#F97316`          | `#F97316`          | Hold / degraded                    |
| `--danger` / `--destructive` | `#EF4444`          | `#EF4444`          | Block / unhealthy                  |

### Data series

Used by `lib/chartTheme.ts` for multi-series charts, in order:

| Slot     | Hex       |
| -------- | --------- |
| `data-1` | `#3B82F6` |
| `data-2` | `#8B5CF6` |
| `data-3` | `#EC4899` |
| `data-4` | `#10B981` |
| `data-5` | `#06B6D4` |

Platform badge colours (Meta, Google, TikTok, Snapchat, LinkedIn, WhatsApp)
are **not** theme tokens — they are external brand identities and stay fixed
across themes.

### Geometry

| Token           | Value                    | Use                          |
| --------------- | ------------------------ | ---------------------------- |
| `--radius`      | `1rem` (16px)            | `rounded-2xl` cards, default |
| Radii           | 8 / 12 / 14 / 16 / 18 px | Sm → 2xl                     |
| Card padding    | `p-6` minimum            | Surfaces                     |
| Buttons / pills | `rounded-full`           | All clickable affordances    |

## Theme system

`frontend/src/components/primitives/theme/ThemeProvider.tsx` wraps the
app and exposes:

- `theme: 'dark' | 'light' | 'system'`
- `resolvedTheme: 'dark' | 'light'` (what's actually applied)
- `setTheme(theme)`

Persists to `localStorage('stratum-theme')`. Defaults to `'system'`,
which resolves via `window.matchMedia('(prefers-color-scheme: dark)')`.

The initial paint is handled by an inline `<script>` in
`frontend/index.html` that applies the correct class to `<html>` before
React mounts — this avoids the dreaded theme flash. A
`theme-no-transition` guard on the root suppresses the cross-fade
transition during that initial swap, then is removed on the next
animation frame so user-driven toggles animate smoothly.

`ThemeToggle` (in `primitives/theme/ThemeToggle.tsx`) renders a
segmented sun / moon / system control; lives in the topbar.

## Primitive library

```
frontend/src/components/primitives/
├── Card.tsx              ← rounded-2xl surface, default/elevated/glow variants
├── KPI.tsx               ← composed Card + label + value + delta + status
├── StatusPill.tsx        ← figma signature pill (healthy/degraded/unhealthy/neutral)
├── Chart.tsx             ← themed recharts wrapper (LineChart, AreaChart)
├── DataTable.tsx         ← headless table with sort + loading + empty
├── ConfirmDrawer.tsx     ← destructive-action preview-then-confirm gate
├── nav/
│   ├── Sidebar.tsx           ← collapsible-group nav (Operate/Intelligence/Account)
│   ├── Topbar.tsx            ← search + theme toggle + profile
│   └── dashboardNav.ts       ← IA config (typed group definition)
└── theme/
    ├── ThemeProvider.tsx     ← dark/light/system + localStorage + matchMedia
    └── ThemeToggle.tsx       ← sun/moon/system segmented control
```

Every primitive ships with a vitest at `*.test.tsx`. ARIA + keyboard
support are first-class. Loading / empty / error states are explicit
props on every data-bearing primitive — no caller-side branching
required.

## Dashboard home

`frontend/src/views/dashboard/Overview.tsx` is the post-login
"what needs my attention" surface composed entirely from primitives.

Composition (top → bottom):

1. **KpiStrip** — 4 compact cards (Trust Gate / Signal Health / ROAS /
   Pacing). The most-attention-needing card uses `Card variant="glow"`
   for emphasis.
2. **SignalStrip** — alert chips per severity bucket; click drives
   the FocusPane. Collapses to "All clear" when alerts = 0.
3. **FocusPane** — URL-driven adaptive surface. `?focus=trust-holds`
   renders a DataTable with per-row CTAs; `signal-drops` shows the EMQ
   pipeline view; `pacing-breaches` shows a budget-burn table;
   `autopilot-pending` filters the autopilot stream; `all-clear`
   shows a 30d revenue/spend chart.
4. **RecentAutopilot** — last 24h decisions DataTable, always present.

Data flows through `views/dashboard/overview/useOverviewData.ts` —
the single seam between primitives and the API. It calls the existing
React Query hooks (`useDashboardOverview`, `useTrustStatus`,
`useDashboardSignalHealth`, `usePacingSummary`, `useAutopilotActions`)
in parallel and falls back to deterministic mocks
(`overview/mockData.ts`) when auth/user context is missing (demo /
unauthenticated) or a single endpoint is unavailable. The `isMock`
flag drives a "Demo data" pill in the page header so testers can tell
at a glance.

## Sidebar IA

The product has 25+ dashboard routes; the figma brief asks for a small
number of sidebar groups. `dashboardNavGroups` (in `nav/dashboardNav.ts`)
reconciles by splitting the routes into 3 collapsible groups:

```
Operate       Overview · Custom Dashboard · Campaigns · Autopilot ·
              Audiences · Trust Engine · Pacing · Rules · AB Testing ·
              Profit & ROAS
Intelligence  CDP · Attribution · Reporting · Knowledge Graph ·
              AI Insights · AI Recommendations · Cohort/Funnel Analysis ·
              Predictions · Benchmarks · Anomalies · Model Explainability ·
              SQL Editor
Workspace     Integrations · WhatsApp · Newsletter · Drip Campaigns ·
              Push Notifications · Embed Widgets · Audit Log · Compliance ·
              Data & Privacy · API Keys · Settings · Team · Billing
```

Platform-owner tooling (feature flags, control tower, credentials,
cross-org analytics) lives in a separate shell at `/console/*`
(`nav/consoleNav.ts`) — the operator dashboard never surfaces it, so
non-owner roles never see it.

The Sidebar primitive auto-expands the group containing the active
route on mount and on route changes — no manual expand needed when
navigating from an Overview into a CDP sub-page. Collapse state
persists per-user via `localStorage('stratum-sidebar-groups')`.

> **Known gap**: the `Billing` nav item (`/dashboard/settings/billing`)
> and its `CreditCard` icon are dead — Payments/Stripe was removed in
> the single-client conversion and no route or backend endpoint
> answers it (falls through to the default Settings tab). Not fixed
> here; tracked as a deferred cleanup in
> `docs/single-client-conversion.md`.

## Migrations

The legacy "Nebula Aurora" theme (cyber-pink `#FF1F6D`, midnight
`#080C14`, Satoshi + Clash Display) is fully retired across the
codebase via the 6-phase commit chain
`a189ff6 → 36a86c0`. The `frontend/scripts/sweep-hex.sh` script remains
in the repo for catching future palette stragglers. The doc
`nebula-aurora-design.md` is now historical reference only.

## When in doubt

- **Use semantic Tailwind tokens** (`bg-card`, `text-foreground`,
  `border-border`, `text-primary`) over hardcoded hex.
- **Use `text-muted-foreground`** instead of `text-gray-400 dark:text-gray-300`.
- **Compose primitives** before building bespoke surfaces.
- **Glow only for primary KPI** — overuse cheapens the effect.
- **Mono for labels and status**, Geist for body and display.

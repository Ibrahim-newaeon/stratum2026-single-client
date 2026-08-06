# Claymorphism Theme — ADs Growth System

The dashboard, auth flow, and marketing surfaces read a claymorphism theme
("vivid jewel clay", 2026-08): plush dark clay surfaces with layered inner/
outer shadows, embossed type, pill-shaped controls, and a jewel accent
palette. Dual-mode via semantic CSS variables in `frontend/src/index.css`
and Tailwind aliases in `frontend/tailwind.config.js`.

> **This file has been wrong before.** It described ink + ember long after
> the code moved to Opal gold, and SuperAds blue long after the move to
> clay. `frontend/src/index.css` is the only authority; these tables are a
> convenience copy.

## Tokens

### Surfaces

| Token                  | Dark                        | Light                      | Use             |
| ---------------------- | --------------------------- | -------------------------- | --------------- |
| `--background`         | `#0D0C13` indigo obsidian   | `#EFEEF7` lavender porcelain | Page bg       |
| `--card`               | `#1A1821` raised clay       | `#F9F9FC`                  | Card / panel bg |
| `--popover`            | `#24212C` elevated clay     | `#FFFFFF`                  | Overlays        |
| `--surface-tertiary`   | `#24212C`                   | sunken porcelain           | Elevated card   |
| `--muted`              | `#282531` sunken fill       | sunken porcelain           | Subtle fills    |
| `--border` / `--input` | clay seam                   | porcelain seam             | Borders         |

### Typography

| Token                     | Dark             | Light            | Use                     |
| ------------------------- | ---------------- | ---------------- | ----------------------- |
| `--foreground`            | `#EFEFF7` porcelain white | `#201D2B` | Primary text            |
| `--muted-foreground`      | `#A9A6BD` cool putty | `#625E76`    | Secondary text          |
| Font family `font-sans`   | Inter            | Inter            | Body                    |
| Font family `font-display`| Space Grotesk    | Space Grotesk    | Headings                |
| Font family `font-mono`   | JetBrains Mono   | JetBrains Mono   | Labels, status, tabular |
| `font-sans-arabic`        | Noto Sans Arabic | Noto Sans Arabic | RTL surfaces            |

### Brand & status (jewel palette)

| Token                        | Dark                    | Light (deepened) | Use                          |
| ---------------------------- | ----------------------- | ---------------- | ---------------------------- |
| `--primary`                  | `#29D6C7` turquoise     | `#148F85`        | CTA, active nav, focus ring  |
| `--secondary`                | `#F5B942` radiant gold  | `#D5910B`        | Accent bars, badges, hovers  |
| `--accent`                   | `#8B5CF6` electric violet | `#7C4FE0`      | Insight surfaces, series-2   |
| `--insight`                  | `#A78BFA` violet glow   | `#7C4FE0`        | Secondary insight            |
| `--success`                  | `#5EEAD3` bright mint   | deep mint        | Healthy / PASS               |
| `--warning`                  | `#FBBF24` bright amber  | deep amber       | Hold / degraded              |
| `--danger` / `--destructive` | `#FF6F59` vivid coral   | deep coral       | Block / unhealthy / CRITICAL |

### Clay depth & type utilities

Defined in `index.css` `@layer components`, driven by per-mode shadow vars:

| Utility            | Effect                                            |
| ------------------ | ------------------------------------------------- |
| `.clay-raised`     | Large molded-clay depth (outer drop + inner emboss) |
| `.clay-raised-sm`  | Small clay depth — pills, badges, compact cards   |
| `.clay-inset`      | Sunken well (inputs, tables, icon wells)          |
| `.clay-pressable`  | Tactile press-down on `:active`                   |
| `.text-embossed`   | Type raised off the clay                          |
| `.text-debossed`   | Type carved into the clay (mono labels)           |
| `.bg-clay-ambient` | Studio-lighting backdrop (turquoise/violet/gold radials), fixed attachment |

### Data series

Used by `lib/chartTheme.ts` for multi-series charts, in order:
turquoise `#29D6C7` · violet `#8B5CF6` · pink `#EC4899` · mint `#5EEAD3` ·
gold `#F5B942`.

Platform badge colours (Meta, Google, TikTok, Snapchat, LinkedIn, WhatsApp)
are **not** theme tokens — they are external brand identities and stay fixed
across themes.

### Geometry

| Token           | Value                    | Use                          |
| --------------- | ------------------------ | ---------------------------- |
| `--radius`      | `1.25rem` (20px)         | Plush clay corners, default  |
| Radii           | 8 / 12 / 14 / 16 / 25 px | Sm → 2xl                     |
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
              Audiences · Trust Engine · Pacing · AB Testing ·
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

Theme lineage: Nebula Aurora (cyber-pink) → ink + ember → Opal Hotel gold →
SuperAds blue → **claymorphism vivid-jewel (current, 2026-08)**. The SuperAds
palette was mechanically remapped to the jewel equivalents across all views
and components (old blues → turquoise, greens → mint, reds → coral,
oranges → amber; platform brand colours untouched). The
`frontend/scripts/sweep-hex.sh` script remains in the repo for catching
future palette stragglers.

## When in doubt

- **Use semantic Tailwind tokens** (`bg-card`, `text-foreground`,
  `border-border`, `text-primary`) over hardcoded hex.
- **Use `text-muted-foreground`** instead of `text-gray-400 dark:text-gray-300`.
- **Compose primitives** before building bespoke surfaces.
- **Glow only for primary KPI** — overuse cheapens the effect.
- **Mono for labels and status**, Geist for body and display.

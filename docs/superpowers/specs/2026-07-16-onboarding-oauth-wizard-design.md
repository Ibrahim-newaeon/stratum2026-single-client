# Onboarding OAuth Wizard Upgrade — Design

**Date:** 2026-07-16
**Status:** Approved (soft gate, full-page redirect + resume, session-dismissible banner)

## Problem

The onboarding wizard's Platform Selection step only records intent
(`selected_platforms` JSONB) — it never connects anything. A user can finish
or skip onboarding with zero live integrations and land on a dashboard
showing demo data, with only an easy-to-miss "Demo data" pill explaining why.

Two existing bugs compound this:

1. **IntegrationsHub Connect is a silent no-op** — the frontend reads
   `res.data.data.auth_url || res.data.data.redirect_url`
   (`IntegrationsHub.tsx:134`) but `POST /oauth/{platform}/authorize` returns
   `authorization_url` (`oauth.py:220-228`). The OAuth handshake never launches
   from the UI.
2. **The OAuth callback redirects to a dead route** — the backend callback
   ends with `RedirectResponse` to `{frontend_url}/connect?platform=X&status=…`
   (`oauth.py:390-393`), but no `/connect` route exists in `App.tsx`.

## Decisions (user-approved)

- **Soft gate**: the wizard never blocks on connection; zero-connection
  Continue is allowed but explicitly labeled and warned.
- **Full-page redirect + resume**: no popups. One platform per round-trip.
  Wizard state survives because steps 1–2 are persisted server-side and the
  wizard already restores `current_step` from `GET /onboarding/status`.
- **Nudge banner**: all dashboard pages, dismissible per session
  (`sessionStorage`), driven by backend truth, shown until the first platform
  is connected.

## Components

### 1. `useConnections()` hook — `frontend/src/api/connections.ts` (new)

React-Query hook wrapping `GET /oauth/status`, `queryKey: ['connections']`.
Exposes `{ platform, status, connected_at, token_expires_at,
ad_accounts_count, error }[]` — field names matching the backend
`ConnectionStatusResponse` (`oauth.py:100-110`); fixes the frontend's current
`expires_at`/`account_count` mismatch. Also exposes a derived
`hasLiveConnection: boolean` (any row with `status === 'connected'`).
IntegrationsHub migrates from its local-useState fetch to this hook.

### 2. Wizard Step 2 rework — `frontend/src/views/Onboarding.tsx`

- Each platform card (meta/google/tiktok/snapchat) renders:
  - live status chip via `StatusPill` (connected → healthy, error → unhealthy,
    disconnected → neutral) from `useConnections()`;
  - a **Connect** button: `POST /oauth/{platform}/authorize` → set
    `sessionStorage['stratum_oauth_return'] = '/onboarding'` →
    `window.location.href = authorization_url`. Disabled with spinner while
    the authorize call is in flight; on API error, toast + error chip.
- Card toggle behavior (intent selection) is kept for platforms not yet
  connected; a connected platform counts as selected and cannot be
  deselected.
- **Continue** submits `POST /onboarding/platform-selection` with
  `platforms = union(connected platforms, toggled cards)`. With zero
  connections AND zero toggles, the step-2 validation currently requiring ≥1
  selection is removed; the button reads **"Continue without connecting"**
  and a warning line appears: dashboard will show demo data until a platform
  is connected.
- On return from OAuth (wizard remount), the wizard restores to step 2 via
  existing `status.current_step` logic; fresh `useConnections()` data shows
  the new chip. No new resume state is required.

### 3. OAuth landing route — `/connect` (new view `OAuthConnectResult.tsx`)

Registered in `App.tsx` inside the authenticated area. Behavior:

- Parse `?platform=&status=&error=`.
- `queryClient.invalidateQueries(['connections'])` and `(['onboarding'])`.
- Toast: success → "«Platform» connected"; error → the error param.
- Redirect (replace) to `sessionStorage['stratum_oauth_return']`, falling
  back to `/dashboard/settings?tab=integrations`; clear the key.
- Renders only a brief spinner; it is a router, not a page.
- Also register the same component at `/dashboard/campaigns/connect` to
  un-dead the existing links from IntegrationsHub (`:313, :350`) and
  `Settings.tsx` (`:1579, :1590`).

### 4. IntegrationsHub Connect fix — `IntegrationsHub.tsx:127-145`

Read `authorization_url` (keep the old keys as fallbacks), set
`stratum_oauth_return` to the current location before redirecting, and
migrate status reads to `useConnections()`.

### 5. `ConnectNudgeBanner` — `frontend/src/components/onboarding/ConnectNudgeBanner.tsx` (new)

Mounted in `DashboardLayout.tsx` beside the existing checklist mount (~:302).
Render condition (all must hold):

- `GET /onboarding/check` not required (status `skipped` or `completed`);
- `useConnections().hasLiveConnection === false`;
- `sessionStorage['stratum_connect_nudge_dismissed'] !== 'true'`.

Slim `Card` bar: warning icon + "You're viewing demo data — connect your
first ad platform to go live" + **Connect now** (→
`/dashboard/settings?tab=integrations`) + X (sets the sessionStorage key).
While connection status is loading, render nothing (no flash).

### 6. OnboardingChecklist touch-up (one line of honesty)

The `connect_platform` checklist item's completed state now derives from
`useConnections().hasLiveConnection` instead of the optimistic
localStorage mark. No other checklist changes.

## Backend changes

One line: `PlatformSelectionRequest.platforms` currently has `min_length=1`
(`endpoints/onboarding.py:94-98`), which would 422 the soft-gate
zero-connection Continue. Relax to allow an empty list (validator for
platform names stays). All other endpoints are used as-is.

## Error handling

- Authorize call fails → toast + error chip on that card; wizard usable.
- OAuth denied/failed at platform → callback redirects with `status=error` →
  landing toasts and returns to origin; step 2 shows error chip
  (`/oauth/status` reports the connection row's `error`).
- `/connect` reached with no params or no return key → silent redirect to
  integrations settings.
- Platform outage never blocks wizard completion (soft gate).

## Testing

- Vitest: `useConnections` (fetch + derive), `ConnectNudgeBanner` (render
  matrix: skipped×connections×dismissed), `OAuthConnectResult` (param
  parsing, invalidation, redirect), Onboarding step-2 (connect button fires
  authorize + stores return path; zero-connection Continue relabels).
- Existing Onboarding tests updated for removed ≥1-platform validation.
- Manual E2E on Railway with one real platform (user-driven; needs real ad
  creds — currently pending in `stratum-ai.env`).

## Out of scope

- Ad-account picking/enabling after connect (stays in IntegrationsHub).
- CRM / WhatsApp connections in the wizard.
- Popup-based OAuth flow.
- Rewriting the localStorage-driven OnboardingChecklist.

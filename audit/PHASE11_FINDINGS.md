# PHASE 11 — FRONTEND / UI WIRING
Audit date: 2026-07-18.

## Scope declared
Dead nav/routes; `localStorage`/`sessionStorage` tenant-prefixed keys; hardcoded tenant subdomains/hosts; legacy-redirect correctness; onboarding "create org" flows; loading/error states on routes whose APIs now 404. Findings: **5** (0 CRITICAL, 4 MEDIUM, 1 LOW). Several NEEDS-REMOVAL dead-code items.

## OPERATIONAL / CLEAN (evidence-backed)
- **Storage keys carry no tenant prefix.** All 25 keys are `stratum_*`/`stratum-*`/token keys (full list in RESIDUE addendum). `appStore` persist is explicitly de-tenanted ("no tenant context, no tenant ID", appStore.ts:5) and partializes only UI prefs. The one scoping key is `stratum-client-context` (client-switcher, tied to 11-3), not a tenant key.
- **Legacy redirects land on real routes.** `LegacyTenantRedirect` (/app/:tenantId/*→/dashboard), `LegacyAmTenantRedirect` (am/tenant/:id→am/account/:id), `LegacySuperadminRedirect` (/dashboard/superadmin/*→/console), all `/dashboard/owner*`→/console*, /overview→/dashboard/overview — every enumerated target exists. Only theoretical gap: an arbitrary unknown tail on the two wildcard redirects bounces to NotFound (LOW, edge).
- **Onboarding has no "create/choose organization" residue.** Signup collects name/email/phone/password only (Signup.tsx:39-43); the 5-step wizard is Business Profile / Platform / Goals / Automation / Trust-Gate (Onboarding.tsx:193-216) — no org-creation step. Copy correctly says "Ask your organization owner for an invite." Only vestige: a hardcoded `company_website:''` payload field (dead, NEEDS-REMOVAL).
- **No `https://{tenant}.*` interpolated subdomains** anywhere (the tenant-subdomain-in-links hazard is absent).
- **Known dead tenantId props don't break render**: `EmergencyStop`/`TrustGatePanel` receive `tid` defaulting to `1` (Overview.tsx:44) and render fine; `AttributionVariancePanel`/`SignalHealthPanel`/`AutopilotPanel`/`TrustBanner` are not mounted anywhere (dead components).

## FINDINGS

```
FINDING-11-1
Feature:        FEAT-182 (AM Portfolio / Account Narrative views)
Status:         BROKEN
Severity:       MEDIUM
Confidence:     HIGH (CONFIRMED)
What is broken: When their backend API 404s (the /admin/tenants router was deleted — FINDING-5-2),
                the AM Portfolio and Account Narrative pages render HARDCODED FABRICATED sample data
                presented as real — not an error or empty state. A user reaching these pages sees
                fake client accounts with fake plan tiers and MRR.
Root cause:     Portfolio.tsx:72-92 `accountsData?.items?.map(...) ?? [ {name:'Acme Corporation'…},
                {TechStart…}, … ]` — the `?? [fallback]` renders 5 fabricated accounts when
                useTenants() returns undefined (404). AccountNarrative.tsx:94-264 falls back to a
                hardcoded "Fashion Forward" account. Pages reachable via route (App.tsx:1470,1478)
                and LegacyAmTenantRedirect (am/tenant/:id), though not in the sidebar.
Blast radius:   Fabricated account/MRR/plan-tier data shown as if real — the "fabricated value
                presented as real" anti-pattern. Misleads anyone who bookmarks/deep-links these AM
                pages. Also surfaces removed multi-tenant billing concepts (plan tiers, MRR).
Evidence:       Portfolio.tsx:68 useTenants(); :89 `?? [{name:'Acme Corporation'…}]`; in-file NOTE
                (:7-13) admits the data source "does not exist". admin.ts:135 GET /admin/tenants (no
                backend router).
Fix:            Remove the AM views + the admin-tenant API layer (api/admin.ts) — a multi-tenant
                portfolio concept has no meaning in single-org; OR repoint to /clients with a real
                empty/error state (never a fabricated fallback).
Confirm via:    Navigate /dashboard/am/portfolio → shows "Acme Corporation" etc. despite 404 on
                /api/v1/admin/tenants.
```

```
FINDING-11-2
Feature:        FEAT-182 (operator dashboard Overview — primary post-login surface)
Status:         BROKEN
Severity:       MEDIUM
Confidence:     HIGH (CONFIRMED)
What is broken: The Overview page's "View details" and playbook-click actions navigate to
                `/tenant/${tid}/signal-hub` (operate/Overview.tsx:215,224) — a route shape that no
                longer exists. It matches no route and falls to the top-level `*` catch-all →
                NotFound (App.tsx:1724). Dead navigation on the primary dashboard.
Root cause:     Nav path still uses the old per-tenant URL shape `/tenant/:tid/...` instead of the
                current `/dashboard/signal-hub`. Left over from the tenant-scoped routing.
Blast radius:   Clicking a signal/playbook CTA on the main post-login Overview dead-ends at 404.
                Higher visibility than the AM views (this is the default dashboard home).
Evidence:       Overview.tsx:215 `navigate('/tenant/${tid}/signal-hub')`; :224 with `?issue=`. No
                `/tenant/:tid/*` route (only `/dashboard/signal-hub` and `/app/:tenantId/*`).
Fix:            Change to `navigate('/dashboard/signal-hub'...)` (+ query). Add an e2e assertion on
                the Overview CTAs.
Confirm via:    Click "View details" on an Overview signal → lands on NotFound.
```

```
FINDING-11-3
Feature:        FEAT-182 (dashboard header — client context switcher)
Status:         BROKEN
Severity:       MEDIUM
Confidence:     HIGH (CONFIRMED)
What is broken: ClientContextSwitcher is rendered in the dashboard header for MANAGER and ANALYST
                roles (DashboardLayout.tsx:35,177) and calls GET /users/me/assigned-clients on mount
                (ClientContextSwitcher.tsx:111) — an endpoint that does NOT exist in the backend
                (grep users.py/clients.py = 0). The .catch() is silent, so the control perpetually
                displays "Select Client" and never populates. It persists activeClientId to
                localStorage `stratum-client-context`.
Root cause:     Either multi-tenant "switch context" UI residue, or a client-scoping feature whose
                backend endpoint was never built/was removed. Client (agency's customer account) is
                a valid single-org concept (FEAT-061 /clients exists), but the assigned-clients
                endpoint the switcher needs is missing.
Blast radius:   A visible, permanently-non-functional "Select Client" dropdown in the header for all
                manager/analyst users. Confusing; implies a broken/absent capability.
Evidence:       ClientContextSwitcher.tsx:105-116 role gate + apiClient.get('/users/me/assigned-
                clients'); DashboardLayout.tsx:177 renders it; no matching backend route.
Fix:            If client-scoping is intended: implement GET /users/me/assigned-clients (and wire it
                to the /clients data). If not: remove the switcher + `stratum-client-context` key.
Confirm via:    Log in as manager → header shows "Select Client"; Network shows 404 on
                /api/v1/users/me/assigned-clients.
```

```
FINDING-11-4
Feature:        Multiple views (AI Insights, Compliance, Integration Hub, Cohort/Funnel, Developer,
                Push, SQL Editor, Drip) — API base host
Status:         DEGRADED
Severity:       MEDIUM
Confidence:     HIGH
What is broken: 9 views bypass the shared axios client (whose baseURL is the relative '/api/v1',
                client.ts:12) and use raw fetch against a hardcoded fallback host
                `https://api.stratumai.app/api/v1` (`VITE_API_URL || 'https://api.stratumai.app/api/v1'`).
                If VITE_API_URL is unset at build, these pages call the SaaS host api.stratumai.app —
                wrong for a single-client (Opal Hotel) deployment — instead of the deploy's own API.
Root cause:     Per-view API_URL constants with a stale SaaS-host fallback, inconsistent with the
                relative-path apiClient the rest of the app uses.
Blast radius:   If VITE_API_URL is not injected, 9 feature pages make cross-origin calls to the wrong
                host (CORS failures / hitting the multi-tenant SaaS). Even when set, it is a
                divergent, fragile pattern. (Several of these views also 404 via Phase 5 double-
                prefix — AIInsights, ComplianceDashboard — so they are doubly broken.)
Evidence:       AIInsights.tsx:50, ComplianceDashboard.tsx:16, IntegrationHub.tsx:17,
                DripCampaignBuilder.tsx:258, CohortAnalysis.tsx:29, DeveloperPortal.tsx:18,
                FunnelAnalysis.tsx:34, PushNotifications.tsx:52, SQLEditor.tsx:22.
Fix:            Route these through the shared apiClient (relative /api/v1), or centralize API_URL to
                one env-driven constant with no SaaS-host fallback. Ensure VITE_API_URL is set in the
                single-client build.
Confirm via:    Build without VITE_API_URL; open AI Insights → requests go to api.stratumai.app.
```

```
FINDING-11-5
Feature:        Console/analytics pages whose APIs 404 (Phase 5) — error UX
Status:         DEGRADED
Severity:       LOW
Confidence:     HIGH
What is broken: The pages whose backend paths 404 from the double-prefix bug (FINDING-5-1) mostly do
                NOT crash or infinite-spin, but they degrade to SILENT empty/zero states with no
                error indication — the user cannot tell "broken" from "genuinely empty". Worst:
                ComplianceDashboard wraps its fetch in `catch (e) { /* ignore */ }` (ComplianceDash.
                tsx:~101) → blank dashboard. AuditServices shows a "0" empty state, no error branch.
                (Better: PlatformAnalytics and ControlTower pass error/fallback props.)
Root cause:     Missing isError branches; errors swallowed. Compounds Phase 5's 404s by hiding them.
Blast radius:   Broken owner/compliance/audit pages look like empty-but-working pages — the failure
                is invisible, delaying detection (this is partly why 5-1 could ship).
Evidence:       ComplianceDashboard.tsx catch-ignore; AuditServices.tsx:130 empty-only state.
Fix:            Add explicit error states; surface fetch failures. (Root fix is 5-1 itself.)
Confirm via:    Open Compliance Dashboard → blank, no error, despite 404s in Network.
```

## NEEDS-REMOVAL (dead code, not findings)
- **Billing nav item** (dashboardNav.ts:526 → /dashboard/settings/billing) — falls through gracefully to Settings default tab (no crash), but dead. Remove with billing surface (cross-ref FINDING-9 N9-3, FEAT-155).
- **Dead components** (defined with tenantId props, mounted nowhere): AttributionVariancePanel, SignalHealthPanel, AutopilotPanel, TrustBanner/TrustBannerCompact.
- **Dead admin-tenant API layer**: `api/admin.ts` (Tenant/TenantWithMetrics/PlanTier types, useTenants/useTenant/create/suspend/reactivate/getTenantUsers) — consumed only by the dead AM views (11-1).
- **Schema residue**: `User.tenantId`, `CreateUserRequest.tenantId`, `UpdateUserRequest.tenantId` type fields (admin.ts:21,70,76); `company_website:''` signup field; `ConsentManager useConsentStats(tenantId)` param name.

## Phase 11 summary
No CRITICAL, but the frontend carries more live-visible residue than the backend phases: the primary Overview page has a dead `/tenant/:tid/...` CTA (11-2), the header shows a permanently-empty "Select Client" switcher for manager/analyst roles (11-3), 9 views hardcode the wrong SaaS API host (11-4), and — most notable — the AM Portfolio/Narrative pages render FABRICATED sample accounts (with plan tiers/MRR) instead of erroring when their deleted API 404s (11-1). Storage, redirects, and onboarding are clean of tenant residue. The Phase-5 404 pages fail *silently* (11-5), which is precisely why that breakage went unnoticed. Bulk dead-code (admin-tenant layer, 4 dead panels, Billing nav) should be swept.

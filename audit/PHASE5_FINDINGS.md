# PHASE 5 — API ENDPOINT AUDIT
Audit date: 2026-07-18.

## Scope declared
Routes still expecting `:tenantId` path params; the 4 stacked-prefix routers; response DTOs emitting removed tenant fields; pagination/filter/sort; rate-limit key collapse (self-DoS); CORS from tenant domains; unregistered routers; FE↔BE path agreement. Healthy = clean paths, per-principal limiting, no tenant-derived CORS. Findings this phase: **4** (0 CRITICAL, 1 HIGH, 3 MEDIUM — all BROKEN, all CONFIRMED first-hand).

## What is HEALTHY (evidence-backed)
- **Rate limiting is per-principal, NOT tenant-bucketed → no self-DoS.** `RateLimitMiddleware` IS installed (`main.py:382`, executes inner of AuthContext so authed requests key by user). Key = `user:{user_id}` if authenticated else `ip:{ip}` (`rate_limit.py:240-245`). The audit's "per-tenant limit keys collapsed into one global bucket" hazard is **absent** — there was never a tenant key here. Auth endpoints get stricter sub-limits (`rate_limit.py:90-95`). Redis sliding-window with in-memory fallback.
- **CORS has no tenant-subdomain construction.** Origins = env `cors_origins` (comma list) + `frontend_url`, trimmed (`config.py:266-280`). No wildcard-subdomain, no per-tenant origin derivation. Single explicit allow-list.
- **No tenant path params or tenant headers in live requests.** FE sends no `X-Tenant-ID` (asserted by `client.test.ts:110-115`), no `tenant_id=` query param. Only the intentional legacy react-router redirects use `:tenantId` (client-side nav, not API).
- **Pagination/filter/sort intact**: FE passes `?days=`, `?page=`, `?page_size=`, `?period=`, `?platform=`, `?status=` query params; backend handlers accept them. No param-shape breakage found — the 404s below are prefix-routing bugs, not pagination bugs.
- **`/analytics/tenant-overview` is orphaned but not a 404 risk**: the only FE reference is a comment (`hooks.ts:301`); the live consumer `useAccountOverview` calls `/dashboard/overview` (hooks.ts:311). Backend endpoint is dead code (RESIDUE N-1), not a broken contract.

## FINDINGS

```
FINDING-5-1
Feature:        FEAT-038 (owner Platform Analytics), FEAT-052 (Audit Services),
                FEAT-070 (AI Intelligence), FEAT-072 (Enterprise Compliance)
Status:         BROKEN
Severity:       HIGH
Confidence:     HIGH (CONFIRMED — both sides read first-hand)
What is broken: FOUR routers are mounted with a registry prefix ON TOP OF the module's own
                already-complete APIRouter prefix, producing double-nested served paths. The
                frontend calls the SINGLE-prefix path (what the module author intended), so
                EVERY call to these four feature areas 404s. All four confirmed by reading both
                the served path and the FE call site:

                | Router | Served (real) path | FE calls | Result |
                |---|---|---|---|
                | console_analytics | /api/v1/console/analytics/console/platform-overview | /api/v1/console/platform-overview (consoleAnalytics.ts:68,84,100) | 404 |
                | audit_services | /api/v1/audit/audit-services/* | /api/v1/audit-services/* (auditServices.ts, auditServicesPages.ts, emqMeasure.ts — 19 call sites) | 404 |
                | intelligence | /api/v1/intelligence/analytics/insights/nlq | /api/v1/analytics/insights/nlq (AIInsights.tsx:119,269,442) | 404 |
                | compliance | /api/v1/compliance/admin/compliance/audit-log/search | /api/v1/admin/compliance/audit-log/search (ComplianceDashboard.tsx:91,206,323,336) | 404 |

Root cause:     Registry prefixes in backend/app/api/v1/__init__.py double-prefix routers that
                already declare a full module prefix:
                  - __init__.py:234-235 prefix="/console/analytics" + console_analytics.py:20 prefix="/console"
                  - __init__.py:332-334 prefix="/audit" + audit_services.py:71 prefix="/audit-services"
                  - __init__.py:476-477 prefix="/intelligence" + intelligence.py:27 prefix="/analytics/insights"
                  - __init__.py:491-492 prefix="/compliance" + compliance.py:32-36 prefix="/admin/compliance"
                Likely introduced/exposed during the conversion's router-prefix reorganization
                (route-merge / de-tenanting moved routers to new registry prefixes without
                dropping the module prefix). Verified no sibling router serves the single-prefix
                path: platform-overview, /nlq, experiments exist ONLY in the stacked modules.
Blast radius:   Four owner/admin feature areas are 100% non-functional from the UI, no workaround:
                (1) Platform Analytics (platform-overview, signal-health-trends, actions-analytics);
                (2) Audit Services — offline-conversion upload/batches, A/B experiments start/stop,
                LTV segments, budget-reallocation plan, EMQ measure; (3) AI Insights — NL query,
                anomaly explain, predict; (4) Compliance Dashboard — audit-log search/summary,
                RBAC roles, GDPR retention policy + purge preview. OpenAPI spec advertises the
                double paths, so the drift is self-consistent on the backend but wrong vs FE.
Evidence:       Registry lines + module prefixes quoted above (read directly). FE call literals
                read directly: consoleAnalytics.ts:68 `/console/platform-overview`;
                auditServicesPages.ts:64 `/audit-services/offline-conversions/upload`;
                AIInsights.tsx:119 `${API_URL}/analytics/insights/nlq`;
                ComplianceDashboard.tsx:91 `${API_URL}/admin/compliance/audit-log/search`.
                FE baseURL = /api/v1 (client.ts:11-12; raw-fetch views bake /api/v1 into API_URL).
Fix:            Drop the redundant registry prefix so the served path equals the module prefix
                (preferred — matches FE and the module author's intent):
                  console_analytics → registry prefix "" (module already /console) OR give it a
                  distinct single prefix and update FE; audit_services → registry "" (module
                  /audit-services); intelligence → registry "" (module /analytics/insights);
                  compliance → registry "" (module /admin/compliance).
                Then add a contract test (or generate the FE client from OpenAPI) to prevent recurrence.
Confirm via:    curl /api/v1/audit-services/health → currently 404; curl
                /api/v1/audit/audit-services/health → 200. After fix, the former returns 200.
```

```
FINDING-5-2
Feature:        FEAT-182 (AM Portfolio / Account-Manager views) — API contract
Status:         BROKEN
Severity:       MEDIUM
Confidence:     HIGH (CONFIRMED)
What is broken: 8 live FE functions call /api/v1/admin/tenants* which has NO backend router at
                all (the /admin/tenants management router was removed with multi-tenancy). Exported
                as hooks useTenants/useTenant/useCreateTenant/useUpdateTenant/useDeleteTenant/
                useSuspendTenant/useReactivateTenant/useTenantUsers (admin.ts:242-321), re-exported
                via hooks.ts:38-46, consumed by views/am/Portfolio.tsx:68 (useTenants) and
                views/am/AccountNarrative.tsx:83 (useTenant).
Root cause:     Conversion removed the tenant admin API; the frontend admin-tenant client + the two
                AM views that consume it were left wired. The view files' own header comments
                (Portfolio.tsx:8, AccountNarrative.tsx:8) acknowledge the data source no longer
                exists, but the code paths still execute and 404.
Blast radius:   The Account-Manager Portfolio (/dashboard/am/portfolio) and Account Narrative
                (/dashboard/am/account/:id) pages error on load. Cross-ref Phase 11 (frontend
                dead-view cleanup).
Evidence:       admin.ts:135-176 (8 apiClient.*('/admin/tenants…') calls); no /admin router in
                __init__.py (grep: bare /admin prefix = 0).
Fix:            Remove the admin-tenant client + hooks and the two AM views (or repoint them to
                /clients + /console/analytics if the AM concept is retained as "clients").
Confirm via:    Load /dashboard/am/portfolio → network tab shows 404 on /api/v1/admin/tenants.
```

```
FINDING-5-3
Feature:        FEAT-052 / FEAT-201 (Audit-log stats & export) — API contract
Status:         BROKEN
Severity:       MEDIUM
Confidence:     HIGH (CONFIRMED)
What is broken: FE audit.ts calls /api/v1/audit/stats (audit.ts:104) and /api/v1/audit/export
                (audit.ts:118). The /audit registry prefix ONLY mounts audit_services, whose
                routes all live under /audit/audit-services/… — so no /audit/stats or /audit/export
                route exists. Both 404.
Root cause:     Same prefix confusion as 5-1: /audit is occupied by audit_services (itself mis-
                prefixed), and there is no top-level audit-stats router. The FE file's comment
                (audit.ts:10-11) notes the former /tenants/{id}/audit* path is gone.
Blast radius:   Audit-log stats widget and CSV export action are dead wherever they're rendered.
Fix:            Point FE to the real audit endpoint(s), or add the stats/export routes under the
                corrected audit prefix (depends on 5-1 resolution).
Confirm via:    Trigger audit-log export in UI → 404 on /api/v1/audit/export.
```

```
FINDING-5-4
Feature:        FEAT-067 (Embed Widgets — public serving)
Status:         BROKEN
Severity:       MEDIUM
Confidence:     HIGH (CONFIRMED)
What is broken: The public widget-serving router embed_widgets.public_router (prefix "/embed/v1",
                routes /widget/{widget_id} etc., embed_widgets.py:346-349) is NEVER mounted — only
                the authed embed_widgets.router (/embed-widgets) is registered (__init__.py:455-457;
                grep for public_router include = 0). Additionally, /embed/v1/loader.js has NO
                handler defined at all. Yet the EmbedWidgets UI generates customer embed snippets
                pointing at https://app.stratum.ai/embed/v1/widget/${widget.id} and
                /embed/v1/loader.js (EmbedWidgets.tsx:158,173).
Root cause:     public_router defined but its include_router call is missing; loader.js route never
                implemented. (Also: the embed snippet hardcodes host app.stratum.ai — stale for a
                single-client Opal Hotel deployment; secondary.)
Blast radius:   Every embed code the product hands to external site owners 404s — the entire
                external-embed feature is non-functional. Public, customer-facing.
Evidence:       embed_widgets.py:346 public_router defined; no include anywhere; no loader.js route
                (grep = 0). EmbedWidgets.tsx:158,173 issue /embed/v1/* URLs.
Fix:            Mount public_router (api_router.include_router(embed_widgets.public_router)); add the
                /embed/v1/loader.js handler; parameterize the embed host off frontend_url/config.
Confirm via:    Create a widget, copy its embed URL, GET it → currently 404.
```

## Unregistered routers dispositioned
- `embed_widgets.public_router` → FINDING-5-4 (should be mounted).
- `memory_debug.py` (`/debug/memory`) → NOT registered, NOT consumed by FE. Confirmed dead. **NEEDS-REMOVAL** (Phase 12 cleanup), not a finding — nothing depends on it and it exposes nothing.

## Response-DTO tenant residue (cross-ref)
- `emq_v2` portfolio DTO emits `totalTenants`/`affectedTenants` (FINDING-2-1). FE consumer is `emqMeasure.ts` → which 404s anyway under 5-1, so no FE "choke", but the value is wrong/fabricated per 2-1. No other DTO emits a tenant field a consumer parses.

## Phase 5 summary
Infrastructure-level API concerns are **clean**: rate limiting is per-principal (no self-DoS), CORS carries no tenant wildcard, no tenant path params/headers, pagination intact. The damage is a **routing-contract break**: a double-prefix mistake on four routers (5-1, HIGH) plus three orphaned FE→BE contracts (admin/tenants, audit stats/export, embed public) — together taking down owner Platform Analytics, Audit Services, AI Insights, Compliance, the AM Portfolio views, audit export, and external embeds. All are BROKEN with no workaround and all CONFIRMED by reading both ends. Notably these are all **owner/admin/external secondary surfaces** — which is why they plausibly survived a core-flow smoke test (the login/campaign/dashboard happy path is unaffected). This is the strongest signal so far that post-conversion runtime verification (Phase 13) is needed and that a generated/typed API client would have caught 5-1 at build time.

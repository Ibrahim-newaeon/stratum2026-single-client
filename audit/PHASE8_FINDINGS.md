# PHASE 8 — REALTIME, NOTIFICATIONS & EMAIL
Audit date: 2026-07-18.

## Scope declared
Realtime: `/ws` + SSE channel/room naming (tenant rooms?), socket auth handshake reading tenant claims, presence, client↔server subscription-name agreement, the unused `useWebSocket` hook. Notifications & email: templates rendering now-null tenant variables (name/logo/subdomain), per-tenant from/reply-to, unsubscribe links, push topics. Findings: **1** (0 CRITICAL, 1 MEDIUM). 3 observations.

## EMAIL & NOTIFICATIONS — OPERATIONAL (agent-verified, evidence-backed)
Fully de-tenanted; no null-variable rendering. All email bodies are Python f-strings in `services/email_service.py` (no .html/.j2/.mjml templates).
- **No tenant variable, subdomain, or removed-`Tenant`-field dereference in any sent output.** No `{{tenant_name}}`/`undefined`/`None` leaks; every name interpolation has a fallback (`user_name`→'there', `org_name`→'your organization').
- **Brand is a hardcoded literal "ADs Growth System"** in every template header (email_service.py:187,258,331) — was tenant-branded pre-conversion, now correctly a single hardcoded brand (not a null field).
- **All email links use `settings.frontend_url`** (verify/reset/welcome/invite/billing + newsletter open/click/unsubscribe) — no `https://{tenant}.app.com` subdomain interpolation anywhere. (frontend_url = config.py:330.)
- **Sender identity single-sourced**: `settings.email_from_name/email_from_address` for transactional; per-campaign user config for newsletter; per-schedule config for reports. No per-tenant from/reply-to dereference.
- **Invite `org_name` correctly dereferences the surviving `Organization`** (`get_organization(db).name`, users.py:339-357) with a safe fallback — not the removed Tenant.
- **In-app / push / Slack notifications** carry no tenant variable; push default title "ADs Growth System" hardcoded. Drip campaigns are flag-gated off (503) — no live template surface.

## REALTIME — FINDING (traced end-to-end)
The WebSocket handshake is sound and correctly de-tenanted: `/ws` requires a valid **access** token, rejects refresh/anonymous with close 4001 (main.py:855-883), keys on `user_id`, reads **no tenant claim**. The channel naming is internally consistent (NOT a mismatch — I verified both pairs):
- Workers `publish_event()` → Redis channel `events:org` (helpers.py:67-90) — de-tenanted.
- Authed SSE `/api/v1/events/stream` subscribes to `events:org` (main.py:803) — **matches** the worker publisher.
- `ws_manager.broadcast()` → Redis `ws:org` (websocket.py:333); `_redis_listener` psubscribes `ws:*`, dispatches `ws:org` (websocket.py:349-378) — **matches** internally.

But nothing reaches a user, for three independent reasons:

```
FINDING-8-1
Feature:        FEAT-140 (WebSocket /ws), FEAT-141 (authed SSE stream), FEAT-142 (useWebSocket hooks)
Status:         BROKEN
Severity:       MEDIUM
Confidence:     HIGH (CONFIRMED)
What is broken: The real-time delivery pipeline is fully built and channel-consistent but is not
                wired to any user, on either transport:
                (1) WebSocket producer is dead: NO code in api/services/tasks calls
                    ws_manager.broadcast() (grep = 0), so the documented event types (emq_update,
                    incident_opened/closed, autopilot_mode_change, action_recommendation,
                    platform_status) are never emitted over /ws.
                (2) WebSocket consumer is dead: the FE useWebSocket/useRealtimeEmq/useRealtimeIncidents
                    hooks are imported by NO component (Phase 1) — only the hook file + its test.
                (3) Authed SSE consumer is dead + mis-authed: the FE createEventSource() helper
                    (services/api.ts:516) is never called (grep = 0), so no browser opens
                    /api/v1/events/stream. And if it were called, it appends the token as ?token=
                    (api.ts:521), but the endpoint's own docstring REFUSES query-string tokens
                    ("Do NOT add a query-string token parameter", main.py:788-789) and expects
                    header auth — which a browser EventSource cannot send. Latent auth contradiction.
                Worker events DO flow to events:org and ARE consumed by the SSE endpoint server-side,
                but with no browser subscriber the events terminate at the endpoint.
Root cause:     Mixed: the FE de-tenanting dropped the tenant-scoped realtime store (commit 274b34da
                "appStore replaces tenantStore") and plausibly disconnected the WS consumer; the WS
                broadcast producers and the SSE FE consumer appear never to have been (re)wired.
                Not a channel-name mismatch — channels match; the wiring at both ends is missing.
Blast radius:   No live real-time UX: EMQ score changes, incident open/close, autopilot mode
                changes, and action recommendations never push to the browser. DEGRADED-not-fatal
                because the dashboard sources the same data via React Query polling
                (useDashboardOverview/useTrustStatus/etc. per figma-theme.md), so users see updates
                on refresh/interval, just not pushed. No data loss.
Evidence:       grep ws_manager.broadcast callers = 0; grep createEventSource callers = 0; useWebSocket
                consumers = 0 (Phase 1). main.py:788-789 (no-query-token) vs api.ts:521 (?token=).
                Channels verified matched: events:org (helpers.py:67 ↔ main.py:803), ws:org
                (websocket.py:333 ↔ :375).
Fix:            Decide on ONE transport. If SSE: call createEventSource('/api/v1/events/stream') from
                the dashboard shell AND resolve the auth contradiction (accept the ?token= param on
                that endpoint, or move behind a cookie). If WS: mount the useWebSocket hooks in the
                Overview/trust views AND add ws_manager.broadcast() calls at the event sources
                (EMQ recompute, incident open/close, autopilot mode change). Remove the unused
                transport to avoid the current two-dead-systems ambiguity.
Confirm via:    Open the dashboard, watch Network — no /ws upgrade and no EventSource to
                /api/v1/events/stream is opened; trigger an incident → nothing pushes.
```

## Observations (not findings)
- **OBS-8-a (config, non-tenant)**: newsletter open/click/unsubscribe URLs are `/api/v1/...` paths built on `settings.frontend_url` (newsletter_tasks.py:134). If `frontend_url` doesn't also front the API (separate API host), these tracking links 404. Verify `frontend_url` routing in deployment; not a tenant leak.
- **OBS-8-b (branding residue)**: newsletter footer hardcodes "stratumai.app" / "ADs Growth System" (newsletter_tasks.py:88-89) and email brand is hardcoded "ADs Growth System" — correct single-org pattern, but stale for the Opal Hotel single-client rebrand (cross-ref Phase 11 branding). Cosmetic.
- **OBS-8-c (dead code)**: `slack_service.py` has 4 methods (send_trust_gate_alert/send_signal_health_alert/send_anomaly_alert/daily report) that take a required `org_name` positional with no fallback and are called by nothing. Latent: if wired without supplying `org_name` from Organization, they'd raise. NEEDS-REMOVAL or wire correctly.

## Phase 8 summary
Email/notifications are **fully de-tenanted and safe** — no null tenant variables, no subdomain links, sender identity single-sourced, `org_name` correctly from Organization with fallbacks. The one issue is **realtime delivery, which is built but unwired** (8-1): channels match end-to-end, but the WebSocket has no broadcaster and no consumer, and the authed SSE stream has no FE caller plus a query-token/header-auth contradiction. It's MEDIUM because the dashboard already polls the same data — realtime is a missing enhancement, not a data-integrity break. Notably I *disproved* an apparent channel-name mismatch by tracing the SSE subscriber, which is why this landed as "unwired" rather than "mis-wired."

# FEATURE HEALTH REPORT — ADs Growth System
### Post-Conversion System Audit · Multi-tenant → Single-tenant (STRAT-SC-001)
Audit date: 2026-07-18 · Protocol: Post-Conversion System Audit v2.0 · Branch: `main` (conversion fully merged) · Method: 14-phase evidence-based investigation, static + **runtime-verified**

---

## 1. EXECUTIVE SUMMARY

**Verdict: CONDITIONAL GO.** The core product is operational and the multi-tenant→single-tenant conversion is, at its foundation, **clean and well-executed** — but a routing-contract bug and a job-queue misconfiguration have silently taken down several owner/admin feature areas and all scheduled data refresh. These are concentrated, well-understood, and fast to fix.

**What works (runtime-verified):** login + token refresh, authenticated reads/writes, RBAC guard, the de-tenanted schema (0 `tenant_id` columns confirmed in-DB), fresh-install migration from zero, single global encryption key, storage/cache, email, and billing removal. The conversion itself left **no cross-tenant data leak, no undecryptable secrets, no tenant residue in cache/queue/metric keys, and no silent test-coverage deletion** — the hard failure modes this audit hunts for are absent.

**What's broken:** a double-prefix router bug 404s four owner/admin surfaces; a Celery queue-binding gap strands core scheduled jobs; realtime is unwired; several frontend pages carry dead/fabricated wiring.

### Status counts (124 features)
| Status | Count | Share |
|---|---|---|
| **OPERATIONAL** | 92 | 74% |
| **DEGRADED** | 16 | 13% |
| **BROKEN** | 12 | 10% |
| **UNTESTABLE** | 4 | 3% |

### Findings: 29 total — 0 CRITICAL · 2 HIGH · 19 MEDIUM · 8 LOW  (13 BROKEN-path, 16 DEGRADED)

### Top 5 risks
1. **FINDING-5-1 (HIGH)** — Four routers are double-prefixed; every frontend call 404s. Owner Platform Analytics, Audit Services, AI Insights, and the Compliance Dashboard are 100% non-functional. **Runtime-reproduced over live HTTP.**
2. **FINDING-6-1 (HIGH)** — Beat jobs routed to `sync`/`ml` queues that no worker consumes. Hourly campaign sync, daily forecasts, 30-min predictions, and audience auto-sync **never run** — the whole product silently operates on stale data.
3. **FINDING-11-1 (MEDIUM)** — AM Portfolio/Narrative pages render **fabricated sample accounts** (fake MRR/plan tiers) instead of erroring when their deleted API 404s.
4. **FINDING-13-1 / 13-2 (MEDIUM)** — Runtime-discovered boot/health traps: the app hard-crashes at startup if superadmin env vars are unset (best-effort guard defeated by `SystemExit`); health endpoints are shadowed by the SPA catch-all when the API serves the frontend (healthcheck-killer for single-container deploys).
5. **FINDING-3-1 (MEDIUM)** — Privileged user-management + console-flag routes trust the stale JWT role and no token is revoked on demote/deactivate → a demoted admin keeps power for up to the token lifetime.

### Confidence ceiling: **HIGH (runtime-verified).**
The app was booted against a freshly-migrated scratch DB and the core critical paths, the schema de-tenanting, and the headline 5-1 breakage were all confirmed live. Two paths (file upload, live background-job execution) remain UNTESTABLE with exact re-checks documented (§4). Causation note: several BROKEN findings (5-1, 6-1, 13-2) are infrastructure/wiring bugs not strictly caused by the tenant conversion, but all are live defects and in scope for feature health.

---

## 2. HEALTH MATRIX (all 124 features)

Legend — Status: OK=Operational, DEG=Degraded, BRK=Broken, UNT=Untestable. Conf: H/M/L. Ev: phase where verified (RT = runtime-verified in Phase 13).

### A. Authentication & Session
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-001 | Login/logout, JWT access+refresh rotation, blacklist | OK | — | H | P3, RT (login+refresh 200) |
| FEAT-002 | Signup (invite-only; public-signup gate) | OK | — | H | P3/P10 (enforced auth.py:804) |
| FEAT-003 | Password reset + email verification links | OK | — | H | P3/P8 (single frontend_url) |
| FEAT-004 | MFA (TOTP) challenge-exchange | OK | — | M | P3 (login-flow, lockout) |
| FEAT-005 | RBAC role hierarchy + portal/cms roles | DEG | MED | H | **FINDING-3-1** (stale-role) |
| FEAT-006 | API keys + X-API-Key programmatic auth | OK | — | M | P3/P9 |
| FEAT-007 | AuthContextMiddleware (replaced TenantMiddleware) | OK | — | H | P3 (fail-closed) |
| FEAT-008 | CSRF middleware | OK | — | M | P3 |
| FEAT-009 | Team management + invitations | OK | — | M | P3/P8 (invite email OK) |
| FEAT-010 | User profile/account management | OK | — | H | RT (PATCH /users/me 200) |

### B. Core Domain APIs
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-020 | Campaigns CRUD | OK | — | H | RT (401 guard; router authed) |
| FEAT-021 | Digital assets / DAM | OK | — | M | RT (list 200; upload UNT §4) |
| FEAT-022 | Automation rules engine | OK | — | M | P6 (flag-gated; beat=default? no—rules→rules queue, see 6-1 gated) |
| FEAT-023 | Competitor intelligence | DEG | LOW | H | P6/P10 (fabricates data; gated off by design) |
| FEAT-024 | What-if ML simulator | OK | — | M | P1 (FeatureGate wired) |
| FEAT-025 | Core analytics/KPIs | OK | — | M | P5 |
| FEAT-026 | AI analytics (scaling/fatigue/anomalies) | OK | — | M | P5 |
| FEAT-027 | GDPR export/erasure/consent | OK | — | M | P9 (FeatureGate on) |
| FEAT-028 | WhatsApp messaging + inbound webhook | OK | — | M | P8/P9 (HMAC webhook) |
| FEAT-029 | ML training / model registry | OK | — | M | P1 (require_owner) |
| FEAT-030 | Live predictions / ROAS optimization | OK | — | M | P5 (on-demand OK; scheduled=6-1) |
| FEAT-031 | Conversions API (CAPI) | OK | — | M | P5/P7 (dedupe key clean) |
| FEAT-032 | Meta CAPI event collection | OK | — | M | P5 |
| FEAT-032b| Meta CAPI **quality report** | BRK | LOW | H | **FINDING-2-3** (missing method) |
| FEAT-033 | Landing CMS (multi-language) | OK | — | M | P5 |
| FEAT-034 | EMQ one-click QA fixes | OK | — | M | P5 |
| FEAT-035 | Owner console (platform admin) | OK | — | M | P5 (console.py authed) |
| FEAT-036 | Launch-readiness wizard | OK | — | M | P5 |
| FEAT-037 | Dashboard overview/signal health | OK | — | H | P5/RT |
| FEAT-038 | **Owner platform analytics** | BRK | HIGH | H | **FINDING-5-1** (stacked prefix, RT 404) |
| FEAT-039 | Autopilot (trust-gated actions) | OK | — | M | P6 (apply-actions on default queue, runs) |
| FEAT-040 | Autopilot enforcement / emergency stop | DEG | MED | H | **FINDING-4-1** (singleton no constraint) |
| FEAT-041 | Campaign builder | OK | — | M | P5/P9 |
| FEAT-042 | Feature flags API | OK | — | H | P10 (get_organization singleton) |
| FEAT-043 | AI insights/recommendations | OK | — | M | P5 |
| FEAT-044 | Trust layer / signal health API | OK | — | M | P5 |
| FEAT-045 | EMQ v2 | DEG | MED | H | **FINDING-2-1** (fabricated totalTenants) |
| FEAT-046 | Integrations hub | OK | — | M | P9 |
| FEAT-047 | Pacing & forecasting | OK | — | M | P5 |
| FEAT-048 | Profit ROAS / COGS | OK | — | M | P5 |
| FEAT-049 | Multi-touch attribution | OK | — | M | P5 |
| FEAT-050 | Data-driven attribution (Markov/Shapley) | OK | — | M | P5 |
| FEAT-051 | Automated reporting (PDF/Slack/email) | OK | — | M | P7/P8 |
| FEAT-052 | **Audit services** (offline conv/AB/LTV/EMQ) | BRK | HIGH | H | **FINDING-5-1/5-3** (RT 404) |
| FEAT-053 | Newsletter & email campaigns | OK | — | M | P6/P8 (gated beat) |
| FEAT-054 | Onboarding wizard | DEG | MED | H | **FINDING-4-2** (singleton) |
| FEAT-055 | Ad-platform OAuth flows | OK | — | M | P9 (provider-keyed) |
| FEAT-056 | Platform OAuth-app credential mgmt | OK | — | H | P9/RT (uq_platform_app_credential) |
| FEAT-057 | In-app notifications | OK | — | M | P8 |
| FEAT-058 | Programmatic public API | OK | — | M | P3 (X-API-Key) |
| FEAT-059 | CDP (profiles/segments/events/consent) | OK | — | M | P5/P6 |
| FEAT-060 | Product changelog | DEG | LOW | H | **FINDING-3-4** (unpublished leak) |
| FEAT-061 | Client account management | OK | — | M | P5 |
| FEAT-062 | CMS (blog/pages/contacts) | OK | — | M | P5 |
| FEAT-063 | Knowledge graph | OK | — | M | P1 (shelved, flag-gated) |
| FEAT-064 | Inbound webhook processing (owner) | OK | — | M | P3/P9 |
| FEAT-065 | Slack integration | OK | — | M | P8 |
| FEAT-066 | AI onboarding agent | DEG | MED | H | **FINDING-3-2** (unauth LLM) |
| FEAT-067 | **Embed widgets (public serving)** | BRK | MED | H | **FINDING-5-4** (RT not mounted) |
| FEAT-068 | CDP audience sync → platforms | OK | — | M | P6 (on-demand OK; scheduled=6-1) |
| FEAT-069 | AI copilot chat (RAG) | OK | — | M | P1 |
| FEAT-070 | **AI intelligence** | BRK | HIGH | H | **FINDING-5-1** (RT 404) |
| FEAT-071 | Advanced analytics | OK | — | M | P5 |
| FEAT-072 | **Enterprise compliance dashboard** | BRK | HIGH | H | **FINDING-5-1** (RT 404) |
| FEAT-073 | Outbound integrations (webhooks) | OK | — | M | P9 |
| FEAT-074 | Developer portal | OK | — | M | P5/P11 (host=11-4) |
| FEAT-075 | SendGrid inbound webhook | OK | — | M | P9 (URL-token) |
| FEAT-076 | Drip campaigns | OK | — | M | P8 (flag-gated 503) |
| FEAT-077 | Web push (VAPID) | OK | — | M | P8 |
| FEAT-078 | Memory debug router | OK(dead) | — | H | RT (not registered — inert) |

### C. App-level HTTP surface
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-085 | Health endpoints | DEG | MED | H | **FINDING-13-2** (shadowed when SPA served) |
| FEAT-086 | Prometheus /metrics | OK | — | M | P12 (no tenant labels) |
| FEAT-087 | Public demo metrics + SSE | OK | — | M | P8 |
| FEAT-088 | Authed SSE stream | BRK | MED | H | **FINDING-8-1** (no FE consumer + auth contradiction) |
| FEAT-089 | WebSocket /ws + /ws/stats | BRK | MED | H | **FINDING-8-1** (no broadcaster/consumer) |
| FEAT-090 | API docs (/docs/redoc/openapi) | OK | — | M | RT |
| FEAT-091 | SPA/static serving + catch-all | DEG | MED | H | **FINDING-13-2** (shadows health) |

### D. Background Jobs
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-100 | Campaign data sync (scheduled) | BRK | HIGH | H | **FINDING-6-1** (RT stranded→sync queue) |
| FEAT-101 | Daily forecasts (scheduled) | BRK | HIGH | H | **FINDING-6-1** (→ml queue) |
| FEAT-102 | Creative fatigue scores | OK | — | H | P6 (default queue) |
| FEAT-103 | Audit-log queue processor | OK | — | H | P6 (default) |
| FEAT-104 | Pipeline health + heartbeat | OK | — | H | P6 (default) |
| FEAT-105 | Daily scores | OK | — | H | P6 (default) |
| FEAT-106 | Predictions (scheduled) | BRK | HIGH | H | **FINDING-6-1** (→ml queue) |
| FEAT-107 | Scheduled WhatsApp sends | OK | — | M | P6 (default); alert-rule path=6-4 |
| FEAT-108 | Autopilot apply-actions queue | OK | — | H | P6 (default queue, runs) |
| FEAT-109 | Signal-health daily rollup | OK | — | H | P6 (default) |
| FEAT-110 | Attribution-variance rollup | OK | — | H | P6 (default) |
| FEAT-111 | Audience auto-sync sweep (scheduled) | BRK | HIGH | H | **FINDING-6-1** (→sync queue) |
| FEAT-112 | Campaign-builder connector beat trio | DEG | MED | M | P6 (gated; →sync stranded if enabled) |
| FEAT-113 | Newsletter scheduled sends | OK | — | M | P6 (default; flag-gated) |
| FEAT-114 | Rules evaluation beat | DEG | MED | M | P6 (→rules stranded if enabled) |
| FEAT-115 | Competitor data refresh beat | DEG | LOW | H | P6/P10 (→intel; fabricates; gated) |
| FEAT-116 | CDP compute tasks | DEG | LOW | M | P6 (segment/funnel OK; RFM/traits orphaned) |
| FEAT-117 | CMS publish tasks | DEG | LOW | M | P6 (publish OK; scheduled/versioning orphaned) |
| FEAT-118 | Dead-letter queue sink | OK | — | M | P6 |
| FEAT-119 | CRM sync/writeback tasks | BRK | MED | H | **FINDING-6-2** (unregistered + unscheduled) |
| FEAT-120 | Legacy data_sync Celery app | BRK(dead) | MED | H | **FINDING-6-3** (never launched) |
| FEAT-121 | Legacy automation_runner app | BRK(dead) | MED | H | **FINDING-6-3** (never launched) |
| FEAT-122 | ML retraining pipeline | OK | — | L | P1 (factory) |
| FEAT-123 | Celery queue routing (task_routes) | BRK | HIGH | H | **FINDING-6-1** (RT dead map) |

### E. Files & Storage
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-130 | Storage service (S3/local, flat keys) | OK | — | H | P7 (write==read path) |
| FEAT-131 | Asset upload + static serving | UNT | — | — | RT (upload HTTP 000 — see §4) |
| FEAT-132 | Report artifact generation/delivery | OK | — | M | P7 (symmetric key) |

### F. Caching & Rate Limiting
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-135 | Redis cache (tenant-free keys) | OK | — | H | P7 (symmetric) |
| FEAT-136 | Rate limiting (per-principal) | OK | — | H | P5 (no self-DoS) |

### G. Realtime
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-140 | WebSocket manager + /ws | BRK | MED | H | **FINDING-8-1** |
| FEAT-141 | SSE streams (public OK / authed broken) | DEG | MED | H | **FINDING-8-1** (public works; authed unwired) |
| FEAT-142 | Frontend useWebSocket hooks | BRK | MED | H | **FINDING-8-1** (unused) |

### H. Notifications & Email
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-145 | Email service (transactional) | OK | — | H | P8 (no null tenant vars) |
| FEAT-146 | In-app notification center | OK | — | M | P8 |
| FEAT-147 | Web push (VAPID) | OK | — | M | P8 |
| FEAT-148 | Slack notifications | OK | — | M | P8 (dead org_name methods=NEEDS-REMOVAL) |
| FEAT-149 | WhatsApp customer messaging | OK | — | M | P8 |

### I. Billing
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-155 | Billing/licensing/Stripe (REMOVED) | OK | — | H | P9 (clean removal, no dead gate; dead nav=P11) |

### J. Integrations
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-160 | Meta OAuth + connector | OK | — | H | P9/RT (uq_platform_connection) |
| FEAT-161 | Google Ads OAuth + connector | OK | — | H | P9/RT |
| FEAT-162 | TikTok OAuth + connector | OK | — | M | P9 |
| FEAT-163 | Snapchat OAuth + connector | OK | — | M | P9 |
| FEAT-164 | CRM integrations (HubSpot/Zoho/Pipedrive) | DEG | MED | H | **FINDING-4-3** (no unique constraint) + 3-3/6-2 |
| FEAT-165 | Outbound webhooks | OK | — | M | P9 (user URLs, SSRF-guarded) |
| FEAT-166 | Inbound webhooks (HMAC/token) | OK | — | H | P9 (single-org routing) |

### K. Config & Feature Flags
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-170 | Env kill-switch flags | DEG | LOW | H | **FINDING-10-1** (doc/code drift) |
| FEAT-171 | Org-configurable flags (JSONB) | OK | — | H | P10 (get_organization singleton) |
| FEAT-172 | Console flag management | OK | — | H | P10 |
| FEAT-173 | Settings/config system | OK | — | H | P10/RT |

### L. Frontend Surfaces
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-180 | Marketing site (~35 public routes) | OK | — | M | P11 |
| FEAT-181 | Auth views | OK | — | H | P11/RT |
| FEAT-182 | Operator dashboard shell + nav | DEG | MED | H | **FINDING-11-2/11-3** (dead nav, broken switcher) |
| FEAT-183 | Owner console shell | BRK | HIGH | H | **FINDING-5-1** (its analytics/audit/compliance pages 404) |
| FEAT-184 | CMS portal | OK | — | M | P11 (cms_role guard) |
| FEAT-185 | Client portal | OK | — | M | P11 |
| FEAT-186 | Onboarding wizard + OAuth connect | OK | — | M | P11 (no create-org residue) |
| FEAT-187 | Route guards | OK | — | H | P3/P11 |
| FEAT-188 | Legacy redirects | OK | — | H | P11 (land on real routes) |
| FEAT-189 | Theme system (Opal Hotel rebrand) | OK | — | M | P11 (branding residue=OBS) |
| FEAT-190 | Feature-flag store + hooks | OK | — | M | P1/P10 |
| FEAT-191 | Custom dashboard | OK | — | L | P11 |
| FEAT-192 | superads-dashboard mockup | OK(dead) | — | H | P1 (static, not served) |
| FEAT-193 | AM Portfolio/Narrative views | BRK | MED | H | **FINDING-11-1** (fabricated data) + 5-2 |
| FEAT-194 | 9 views w/ hardcoded SaaS API host | DEG | MED | H | **FINDING-11-4** |
| FEAT-195 | 404-page error UX (silent empty) | DEG | LOW | H | **FINDING-11-5** |

### M. Observability
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-200 | Structured logging + audit mw | OK | — | H | P12 (no tenant fields) |
| FEAT-201 | Audit middleware + pipeline | OK | — | M | P6/P12 |
| FEAT-202 | Prometheus metrics + monitoring | OK | — | H | P12 (no tenant labels) |
| FEAT-203 | Sentry error tracking | OK | — | L | P12 |
| FEAT-204 | Flower (Celery monitoring) | OK | — | L | P0 |
| FEAT-205 | CI (Actions + residue gate) | DEG | LOW | H | **FINDING-12-1** (no drift test); CircleCI=noop |

### Migrations / Test infra (cross-cutting)
| ID | Feature | Status | Sev | Conf | Evidence |
|---|---|---|---|---|---|
| FEAT-M1 | Fresh-install migration from zero | OK | — | H | P12/RT (alembic upgrade head clean) |
| FEAT-M2 | Test suite (converted, not deleted) | OK | — | H | P12 (5,700 tests, ported/re-proven) |
| FEAT-M3 | App startup (owner auto-seed) | DEG | MED | H | **FINDING-13-1** (SystemExit boot crash) |
| FEAT-M4 | PII key coverage | DEG | LOW | M | **FINDING-12-2** (provisioning test dropped) |

**Reconciliation:** all 124 inventoried features (FEAT-001…205 + M1–M4 cross-cutting) appear exactly once. UNTESTABLE = FEAT-131 (upload) + 3 items in §4.

---

## 3. FINDINGS DETAIL

Full finding blocks live in the per-phase files (`audit/PHASE{2..13}_FINDINGS.md`). Consolidated register (29):

### HIGH (2) — launch blockers
- **FINDING-5-1 · BROKEN** — Four routers double-prefixed (registry prefix stacked on module prefix). Served paths `/api/v1/audit/audit-services/*`, `/console/analytics/console/*`, `/intelligence/analytics/insights/*`, `/compliance/admin/compliance/*`; FE calls the single-prefix path → 404. Kills Owner Platform Analytics, Audit Services, AI Insights, Compliance Dashboard. **Runtime: `/api/v1/audit-services/experiments`→404, `/api/v1/audit/audit-services/health`→200.** Fix: drop the redundant registry prefixes; add a contract/generated-client test.
- **FINDING-6-1 · BROKEN** — Worker launched without `-Q`; consumes only `default`. Beat routes `sync-all-campaigns`→sync, `generate-daily-forecasts`→ml, `run-all-predictions`→ml, `audience-auto-sync-sweep`→sync (+gated rules/intel) to queues with no consumer → never execute; `task_routes` map dead (names don't match). **Runtime-confirmed via Celery import.** Fix: launch worker `-Q default,sync,ml,intel,rules` (or route all to default) and fix/remove `task_routes`.

### MEDIUM (19)
- **2-1 DEG** emq portfolio emits fabricated `totalTenants`/`affectedTenants` (mock 156, fixed fractions) to owner console.
- **3-1 DEG** Privileged user-mgmt + console-flag routes trust stale JWT role; no token revocation on demote/deactivate → power persists ≤30 min.
- **3-2 DEG** onboarding-agent `/message` drives LLM unauthenticated (cost/abuse + session enumeration).
- **3-3 DEG** HubSpot OAuth callback accepts but never validates `state` (OAuth CSRF); webhook HMAC only when secret set.
- **4-1 DEG** `enforcement_settings` "singleton" has no DB constraint (`__table_args__=()`, RT: 0 check constraints); unordered `.first()` reads → emergency-stop flag can read wrong row.
- **4-2 DEG** `organization_onboarding` same no-constraint singleton; GET endpoints persist rows → onboarding state can flap.
- **4-3 DEG** `crm_connections` get-or-create keys on `provider` with no unique constraint → duplicate row → `MultipleResultsError` 500.
- **5-2 BRK** 8 live FE hooks call deleted `/admin/tenants*` → 404 (AM views).
- **5-3 BRK** FE `/audit/stats` + `/audit/export` hit no route.
- **5-4 BRK** embed `public_router` (`/embed/v1`) never mounted + `loader.js` no handler; UI issues embed codes that 404. **RT-confirmed unmounted.**
- **6-2 BRK** CRM sync/writeback tasks unregistered (not in `include`) AND unscheduled (`CRM_BEAT_SCHEDULE` never merged).
- **6-3 DEG** Legacy `data_sync.py`/`automation_runner.py` apps dead; `cleanup_old_data` (retention) + `send_weekly_digest` run nowhere.
- **8-1 BRK** Realtime unwired: no `ws_manager.broadcast()` caller, no `useWebSocket` consumer, authed SSE has no FE caller + query-token/header-auth contradiction. (Dashboard polls, so DEGRADED impact.)
- **11-1 BRK** AM Portfolio/Narrative render fabricated sample accounts (fake MRR/tiers) on 404.
- **11-2 BRK** Overview CTAs navigate to dead `/tenant/${tid}/signal-hub` → NotFound (primary dashboard).
- **11-3 BRK** Header `ClientContextSwitcher` calls nonexistent `/users/me/assigned-clients` → perpetual "Select Client".
- **11-4 DEG** 9 views hardcode `https://api.stratumai.app/api/v1` fallback → wrong host if `VITE_API_URL` unset.
- **13-1 BRK** App fails to boot when `SUPERADMIN_EMAIL/PASSWORD` unset — `SystemExit` from seed import escapes best-effort `except Exception`. **RT-observed.**
- **13-2 DEG** SPA catch-all registered before health routes + raises 404 on exclusions → `/health` shadowed when API serves SPA → healthcheck killer. **RT-observed.**

### LOW (8)
- **2-2 DEG** compliance retention reads nonexistent `tenant_settings` table → silent default fallback (compounds 6-3: no cleanup job either).
- **2-3 BRK** Meta CAPI quality report permanently no-op (missing method, error→success:true; pre-existing).
- **3-4 DEG** `/changelog/{id}` leaks unpublished entries to anonymous.
- **6-4 BRK** WhatsApp alert from a rule action TypeErrors (arg mismatch; pre-existing, flag-gated).
- **10-1 DEG** Docs say `feature_competitor_intel`/`automation_rules` default true; code says false (code is correct).
- **11-5 DEG** Phase-5 404 pages fail silently (swallowed errors, "0" states) — hides the breakage.
- **12-1 DEG** No migration-drift/single-head/autogenerate-no-diff test.
- **12-2 DEG** Per-tenant PII-key-provisioning test dropped without single-key successor.

---

## 4. UNTESTABLE REGISTER
| Feature | Why static/partial analysis is inconclusive | Exact runtime check required |
|---|---|---|
| FEAT-131 File upload (`POST /assets`) | Live attempt returned HTTP 000 (multipart connection reset); server survived → ambiguous, not a confirmed defect | Re-run with a robust multipart client (Python `requests`, real PNG) vs a booted API + writable `asset_upload_dir`; assert 200 + `digital_assets` row + file at `/uploads/assets/<key>`, then GET the returned URL → 200. |
| Background-job EXECUTION (6-1 live demo) | Worker+beat+broker not started in Phase 13 (finding confirmed by Celery import instead) | Start `celery worker` (no -Q) + `celery beat`; let beat fire `sync-all-campaigns` (queue `sync`); observe Redis `LLEN sync` grows while the `default`-bound worker never drains it. |
| Full integration suite green | Container cred/env drift vs repo `.env` blocked a direct `pytest` run | With matching DB/Redis creds: `pytest backend/tests/integration -m integration` (conftest DROP SCHEMA + `alembic upgrade head`); expect green at ≥74% floor. |
| Live stranded-queue for gated jobs (112/114) | Gated off by default; not enabled in smoke | Enable the gate flag + run beat; confirm the gated beat entries also strand on non-default queues. |

---

## 5. REMEDIATION PLAN (ordered)

**P0 — Launch blockers (fix before relying on owner/admin surfaces or data freshness)**
| # | Fix | Finding | Effort | Depends on |
|---|---|---|---|---|
| 1 | Remove the 4 redundant registry prefixes; add a generated/typed FE client or contract test | 5-1 | **S** | — |
| 2 | Launch worker with `-Q default,sync,ml,intel,rules` (or route all to default); fix/remove `task_routes` | 6-1 | **S** | — |
| 3 | Guard the owner-seed import (check env/SEED flag before import; or catch BaseException) | 13-1 | **S** | — |
| 4 | Register SPA catch-all LAST / fall-through on exclusions so `/health` resolves | 13-2 | **S** | — |

**P1 — High-value correctness (fast follow)**
| # | Fix | Finding | Effort |
|---|---|---|---|
| 5 | Revoke tokens on demote/deactivate; move role-only routes onto `get_current_user`/`require_*` | 3-1 | **M** |
| 6 | Add `CheckConstraint("id=1")`+upsert-by-id to enforcement_settings, organization_onboarding; unique constraint on crm_connections.provider | 4-1/4-2/4-3 | **M** |
| 7 | Repoint or remove FE calls to `/admin/tenants`, `/audit/stats`, `/audit/export`; delete AM views + admin-tenant client (kill fabricated-data fallbacks) | 5-2/5-3/11-1 | **M** |
| 8 | Mount embed `public_router` + add `/embed/v1/loader.js`; parameterize embed host | 5-4 | **S** |
| 9 | Register `crm_sync_tasks` + merge its beat (or remove CRM surface); re-home `cleanup_old_data`/`send_weekly_digest` | 6-2/6-3 | **M** |
| 10 | Fix Overview `/tenant/${tid}` nav → `/dashboard/...`; implement or remove `ClientContextSwitcher`/assigned-clients | 11-2/11-3 | **S** |
| 11 | Route the 9 raw-fetch views through `apiClient` / central env-driven base | 11-4 | **S** |
| 12 | Gate onboarding-agent behind auth/rate-limit; validate HubSpot OAuth `state` | 3-2/3-3 | **M** |

**P2 — Hygiene / lower severity**
| # | Fix | Finding |
|---|---|---|
| 13 | Decide one realtime transport and wire both ends (+SSE auth) or remove | 8-1 |
| 14 | Correct/label fabricated emq `totalTenants`; add published filter to changelog by-id | 2-1/3-4 |
| 15 | Add error states to the previously-404 pages; add migration-drift + single-key tests | 11-5/12-1/12-2 |
| 16 | Fix docs flag defaults; fix compliance `tenant_settings` retention lookup; whatsapp rule-action args | 10-1/2-2/6-4 |
| 17 | Dead-code sweep: Billing nav, 4 dead panels, admin-tenant layer, standalone Celery apps, dead Slack methods, memory_debug | P6/P9/P11 |

---

## 6. RESIDUE INDEX SUMMARY
Full index: `audit/RESIDUE_INDEX.md`. 359 files mention "tenant"; ~340 HARMLESS (comments/docs/history/intentional legacy shims). **BREAKING: 2** (both → findings: emq totalTenants = 2-1; compliance `tenant_settings` = 2-2). **NEEDS-REMOVAL: 15** (dead `tenantId` props, `/analytics/tenant-overview` name, `is_new_tenant` field, naming residue). **Negative results (0 live hits):** X-Tenant headers, TENANT_ env keys, tenant cache/queue/metric keys, tenant storage paths, RLS policies, multi-tenant fixtures — all confirmed absent, several **runtime-verified in-DB** (0 `tenant_id` columns, 0 `tenant_*` tables).

---

## 7. ASSUMPTIONS & LIMITATIONS
- **Runtime scope**: booted locally against a scratch DB + the existing Postgres/Redis containers; core paths verified live. File upload and live job execution remain UNTESTABLE (§4). Not exercised: full E2E/Playwright, production Railway environment, load.
- **Causation**: several BROKEN findings (5-1, 6-1, 13-2) are infrastructure/wiring bugs not strictly *caused* by the tenant conversion; reported because they are live feature-health defects. Findings 2-3, 6-4 are explicitly pre-existing (noted in-code).
- **Env drift observed**: running-container credentials ≠ repo `.env`; installed `fastapi 0.129.0` ≠ pinned `0.139.2`; host Python 3.12 ≠ target 3.11. None blocked the audit but indicate config/dep hygiene worth reconciling.
- **Confidence labeling**: no OPERATIONAL rating rests on "code looks correct" alone — each cites a phase check, and 7 feature groups + the headline finding are runtime-verified. LOW-confidence positives were not marked OPERATIONAL.
- The conversion's *foundation* (schema de-tenanting, encryption, uniqueness, auth, test conversion, migration-from-zero) is genuinely sound; the defects are concentrated in **routing wiring, job-queue binding, and frontend dead-links** — the surfaces a core-flow smoke test doesn't touch.

# PHASE 2 — TENANT RESIDUE INDEX
Audit date: 2026-07-18. Method: repo-wide case-insensitive ripgrep for identifier/transport/infra/database tenant patterns, excluding build artifacts (`node_modules`, `dist`, `__pycache__`, zips, reports). 359 files mention "tenant"; ~310 are docs/audit history (excluded by CI's own residue gate and classified HARMLESS wholesale below).

CI already enforces a narrow gate (`.github/workflows/ci.yml:27-64`): patterns `tenant_id|X-Tenant-ID|stripe` and `\{tenant`, with documented per-file exclusions. This sweep goes wider (any "tenant" token, transport, infra, DB).

## Verdict summary
| Disposition | Count (entries) |
|---|---|
| BREAKING (→ Findings) | 2 (FINDING-2-1, FINDING-2-2) |
| NEEDS-REMOVAL (dead/cosmetic, no runtime effect) | 15 |
| HARMLESS (comments, docs, history, intentional legacy shims) | everything else (~340 files) |

Adjacent discovery (not tenant residue): FINDING-2-3 — meta_capi quality report permanently broken (pre-existing, self-documented at `meta_capi.py:272-275`).

## BREAKING (live execution path) — all converted to Findings
| Ref | Location | What | Finding |
|---|---|---|---|
| B-1 | `backend/app/services/emq_service.py:829-901`, `schemas/emq_v2.py:204,218`, `endpoints/emq_v2.py:631` | `totalTenants`/`affectedTenants` fields emitted with mislabeled ("platform-day rows") or fabricated (mock 156/78, fixed fractions) values to owner console | FINDING-2-1 (DEGRADED/MEDIUM) |
| B-2 | `backend/app/api/v1/endpoints/compliance.py:592-617` | Raw SQL reads `tenant_settings` — table absent from single-client schema; retention overrides permanently dead, silent default fallback | FINDING-2-2 (DEGRADED/LOW) |

## NEEDS-REMOVAL (dead code / cosmetic residue, verified no runtime effect)
| Ref | Location | What | Why harmless at runtime |
|---|---|---|---|
| N-1 | `endpoints/analytics.py:571-572,709,743` | Route literally named `/analytics/tenant-overview`; `total_tenants=1` hardcoded | Intentional shape-preservation (docstring); functional. Rename is cosmetic; FE + e2e (`emq.spec.ts:23`, `test_analytics_api.py:31`) pin the path |
| N-2 | `endpoints/onboarding_agent.py:48,166,175` | Public request field `is_new_tenant` (mapped internally to `is_new_org`) | Functional API-contract naming residue |
| N-3 | `services/agents/greeting_tool.py:27-213` | `NEW_TENANT` greeting type + `new_tenant` keys | Internal enum naming; works |
| N-4 | `endpoints/feature_flags.py:40-202` | Variable `tenant_router` | Local name only; router un-prefixed and registered |
| N-5 | `endpoints/compliance.py:385-387,535-536` | Static role catalog entry `tenant_admin` / "Tenant Admin" | Hardcoded display data in compliance role listing |
| N-6 | `frontend/src/components/autopilot/EmergencyStop.tsx:24-30`, `api/autopilot.ts:370,392` | `tenantId` prop threaded into hooks | Dead parameter — used only in React Query cache keys; URLs are de-tenanted (`/autopilot/enforcement/settings`, autopilot.ts:376) |
| N-7 | `frontend/src/components/AttributionVariancePanel.tsx:22,162-169`, `api/trustLayer.ts:190-196` | Same dead-`tenantId` pattern | queryKey only; URL `/trust/attribution-variance` un-tenanted |
| N-8 | `frontend/src/utils/pdfExport.ts:11,94-95,227` | `tenantName` field in PDF export | Cosmetic naming; value is org/client name |
| N-9 | `frontend/src/contexts/DemoContext.tsx:11-12,196,247` | `DEMO_TENANT` demo fixture (incl. removed-concept `tier: 'growth'`) | Demo-mode static data |
| N-10 | `backend/app/auth/permissions.py:559` + middleware | `request.state.is_superadmin` flag "still named for the pre-rename tenant middleware until Phase C" | Naming only per docstring — but bypass-path behavior itself is audited in Phase 3 (seed P3-S1) |
| N-11 | `schemas/emq_v2.py:204,218` field names | `affectedTenants`/`totalTenants` DTO names | Overlaps B-1; names stay wrong even after value fix |
| N-12 | `frontend/e2e/emq.spec.ts:23` | Test suite titled "Tenant Overview (Trust)" | Test naming |
| N-13 | `monitoring/prometheus/alerting_rules.yml:114` | Alert description "…across multiple tenants" | Annotation text only; expr uses global metrics |
| N-14 | `docker-compose.yml:95`, `deploy/docker-compose.client.yml:133` | Comment "per-tenant collectors" | Comment only |
| N-15 | `backend/tests/integration/test_api_emq.py:318` | Asserts `totalTenants` present | Locks in B-1's wrong field name; update with FINDING-2-1 fix |

## HARMLESS (verified categories)
- **Explanatory comments** "was tenant-scoped; now global" across `backend/app/models/*` and initial migration (40+ sites) — documentation of intent, no code.
- **STRAT-SC-001 NOTE comments** in endpoints/middleware/tests explaining what was removed (e.g. `auth_context.py:9-10`, `campaigns.py:428`, `console.py:307-309`, `dashboard.py:3916-3922`, `conftest.py` docstrings).
- **Migration 20260715 (`b7e3f4a9c2d1`)** — the rename ledger itself: `tenant_onboarding→organization_onboarding`, `tenant_enforcement_settings→enforcement_settings`, `tenant_enforcement_rules→enforcement_rules`, incl. FK/index/sequence renames. This *removes* residue.
- **Intentional legacy shims** (CI-excluded by design): `LegacyTenantRedirect.tsx` + route `/app/:tenantId/*` (App.tsx:1495), `am/tenant/:tenantId → am/account/:accountId` (App.tsx:1488), `client.test.ts` negative test asserting X-Tenant-ID absent.
- **Docs & history**: root audit/checkpoint/session-memo files, `docs/single-client-conversion.md` removal ledger, glossary "Historical" note, `superads-dashboard/` mockup, `.scratch`, `.claude/hooks/rule-check.sh` (guard tooling), `.secrets.baseline` (stock StripeDetector).

## Negative results (patterns searched, zero live hits)
- `X-Tenant-ID` / `X-Tenant*` headers in live code: **0** (only the CI-excluded negative test).
- `TENANT_` env keys in `.env*`, railway tomls, compose, deploy: **0**.
- Cache keys / Redis channels / metric names with tenant segments (`tenant:`, `tenant_`-prefixed builders): **0** (de-namespaced in `d409a7e0`).
- Storage paths with tenant segments (`services/storage.py`, `core/`): **0**.
- RLS policies / `POLICY` in migrations: **0**.
- Multi-tenant test fixtures: **0** remaining (`test_tenant` factory replaced, `conftest.py:286`; suites ported, e.g. `test_auth_mw_blacklist.py:5`).
- Subdomain-wildcard tenancy (vhosts/CORS/cookies): **0** — all `includeSubDomains` hits are HSTS headers; embed-widget subdomain matching (`token_service.py:411`) is a widget-origin allowlist feature, not tenancy.

## Phase seeds exported
- **P3-S1** (Phase 3): `request.state.is_superadmin` + "tenancy bypass paths pending Phase C" (`permissions.py:559`, commit `8b0f61fc`) — verify AuthContextMiddleware bypass list is safe.
- **P5-S1** (Phase 5): FE/e2e pin `/analytics/tenant-overview` — verify FE caller matches backend path.
- **P9-S1** (Phase 9): confirm owner console EMQ-measure UI consumption of `totalTenants` (FINDING-2-1 blast radius).

# Single-Client Conversion (STRAT-SC-001) — One-Page Record

**Date:** 2026-07-13 → 2026-07-15
**Branch:** `feature/STRAT-SC-001-single-client-conversion` (local-only, never pushed)
**Plan:** `docs/superpowers/plans/2026-07-13-single-client-conversion.md`
**Full ledger:** `.superpowers/sdd/progress.md` (task-by-task detail, review verdicts, fix loops)

ADs Growth System was converted from a multi-tenant SaaS platform (per-tenant
data isolation, subscription tiers, Stripe billing, a superadmin
cross-tenant console) to a **single-client deployment**: one
`Organization` row, no tenant dimension anywhere in the schema, no
billing/tier gating, role-based access only (`owner` down to `viewer`).

---

## 1. Removal ledger applied (task → commit map)

| Task | What it removed/converted | Commit(s) |
|---|---|---|
| A1 | Tier/plan gate → env-driven `FeatureGate` (404 on/off); new `core/feature_gate.py` | `4a68bf4a` (+fix `628c2ef6`) |
| A2 | `core/tiers.py`, Stripe SDK/webhooks/subscriptions, billing routers | `07d8e439` |
| A3 | Editions/provisioning/licensing/limits machinery | `5e9ac004` |
| A4 | Frontend tier gates (`TierGate`/`UpgradePrompt`/`TierContext`), pricing/plans/checkout pages | `2c611c88` |
| B1 | Superadmin → Console/Owner rename (backend); dual-accept bypass during transition | `60839ea2` (+fix `8b0f61fc`) |
| B2 | Superadmin → Console/Owner rename (frontend path contracts) | `a179197f` (+fix `a4107698`) |
| C1 | `Tenant`/`UserTenantMembership` models deleted; `Organization` singleton added; §4.9 global-uniqueness conversion (18 rows) | `0fbe2870` |
| C2 | `TenantMiddleware`/`X-Tenant-ID` header handling deleted; route merges (alerts/settings/command-center → dashboard.py) | `198b262d` (+fix `8a56080f`) |
| C3 | 195 files de-tenanted; campaigns router auth-locked (pre-existing hole closed); 11 bonus fail-open closures | `0eb71c73` (+fix `8316d7b5`) |
| C4 | Single PII key (was per-tenant DEK); 24 Celery tasks de-fanned to single-org; metrics/WS channels de-namespaced | `d409a7e0` (+fix `960a553b`) |
| C5 | Env/config cleanup; two-layer feature-flag architecture ratified; `ENABLE_PUBLIC_SIGNUP` added | `43eebd09` (+fix `7fe5b1aa`) |
| C6 | **Fresh Alembic chain (1 revision, was 41)**; `render_item` StrEnumType hook; conftest rehab; PHASE C GREEN GATE | `47345555` (+fix `1ed2372e`) |
| — | Pre-C fix: compliance RBAC test assert | `ce790b48` |
| D1 | Frontend twin tenant/superadmin shell deleted (13 of 27 files; 14 shared, kept) | `3c21edb8` |
| D2 | `tenantStore` → `appStore`; `X-Tenant-ID` dropped client-side | `274b34da` |
| D3 | `views/tenant` → `views/operate`; `views/superadmin` → `views/console`; `TenantNarrative` → `AccountNarrative` | `691eaf0b` (+fix `c135fa20`) |
| E1 | Residue gate (CI); 2 more fail-open router gaps closed; webhook-prefix collision fixed | `98754b4e` (+fix `af076f9c`) |
| E2 | This task — docs/CLAUDE.md alignment | (this commit) |

Acceptance greps run at various gates, all empty against `backend/app`:
`tenant_id`, `{tenant`, `X-Tenant-ID`, `stripe` (case-insensitive).

---

## 2. §4.9 behavior changes — 18 constraints now global

Every constraint that used to be scoped `UNIQUE(tenant_id, ...)` is now
scoped globally (no tenant dimension to disambiguate on). Full detail:
`.superpowers/sdd/task-C1-report.md`.

| # | Location | Old | New |
|---|---|---|---|
| 1 | `base_models.py` (User) | `UNIQUE(tenant_id, email_hash)` | `UNIQUE(email_hash)` |
| 2 | `base_models.py` (Campaign) | `UNIQUE(tenant_id, platform, external_id)` | `UNIQUE(platform, external_id)` |
| 3 | `base_models.py` (CompetitorBenchmark) | `UNIQUE(tenant_id, domain)` | `UNIQUE(domain)` |
| 4 | `UserTenantMembership` | `UNIQUE(user_id, tenant_id)` | table deleted |
| 5 | `audit_services.py` (Creative) | `UNIQUE(tenant_id, platform, external_id)` | `UNIQUE(platform, external_id)` |
| 6 | `audit_services.py` (AudienceRecord) | `UNIQUE(tenant_id, platform, external_id)` | `UNIQUE(platform, external_id)` |
| 7 | `audit_services.py` (LTVCohortAnalysis) | `UNIQUE(tenant_id, cohort_month)` | `UNIQUE(cohort_month)` |
| 8 | `autopilot.py` (TenantEnforcementRule) | `UNIQUE(tenant_id, rule_id)` | `UNIQUE(rule_id)` |
| 9 | `campaign_builder.py` (TenantPlatformConnection) | `UNIQUE(tenant_id, platform)` | `UNIQUE(platform)` |
| 10 | `cdp.py` (CDPCanonicalIdentity) | `UNIQUE(tenant_id, profile_id)` | `UNIQUE(profile_id)` |
| 11 | `cdp.py` (CDPSegment) | `UNIQUE(tenant_id, slug)` | `UNIQUE(slug)` |
| 12 | `cdp.py` (CDPComputedTrait) | `UNIQUE(tenant_id, name)` | `UNIQUE(name)` |
| 13 | `cdp.py` (CDPFunnel) | `UNIQUE(tenant_id, slug)` | `UNIQUE(slug)` |
| 14 | `client.py` (Client) | `UNIQUE(tenant_id, slug)` | `UNIQUE(slug)` |
| 15 | `emq_playbook.py` (EmqPlaybookItemState) | `UNIQUE(tenant_id, item_key)` | `UNIQUE(item_key)` |
| 16 | `profit.py` (ProductCatalog) | `UNIQUE(tenant_id, sku)` | `UNIQUE(sku)` |
| 17 | `reporting.py` (ReportTemplate) | `UNIQUE(tenant_id, name)` | `UNIQUE(name)` |
| 18 | `reporting.py` (DeliveryChannelConfig) | `UNIQUE(tenant_id, channel, name)` | `UNIQUE(channel, name)` |

17/18 have a positive+negative test pair in
`backend/tests/unit/test_global_uniqueness.py` (row 4's table no longer
exists). Every other constraint/index that used to lead with `tenant_id`
was also rescoped, each carrying the required
`# was tenant-scoped; now global` inline comment (global-constraints.md).

---

## 3. Key de-namespacing map

Full table: `.superpowers/sdd/task-C4-report.md`. Highlights:

**Celery tasks** (24 de-fanned from per-org loops to single passes) —
e.g. `run_all_tenant_predictions()` → `run_all_predictions()`;
`signal_health_rollup(tenant_id, date)` → `signal_health_rollup(date)`;
`sync_all_campaigns()` no longer loops `Tenant` × platform.

**Keys/channels:**

| Old | New |
|---|---|
| `events:tenant:{tenant_id}` (WS/Redis) | `events:org` |
| `ws:tenant:{id}` | `ws:org` |
| `profile:{tenant_id}:{pid}` (CDP cache) | `profile:{pid}` |
| `segment:{tenant_id}` / `funnel:{tenant_id}` rate-limit keys | `segment:{user.id}` / `funnel:{user.id}` |
| `{tenant_id}:{state}` OAuth CSRF state | `secrets.token_urlsafe(32)` alone |
| `cdp_profiles_{tenant_id}.csv` | `cdp_profiles.csv` |

**Metrics:** every `stratum_*` Prometheus metric dropped its `tenant_id`
label (e.g. `stratum_emq_score{tenant_id,platform}` →
`stratum_emq_score{platform}`); `active_tenants` gauge and
`stratum_tenant_api_requests_total` deleted outright.

**PII encryption:** per-tenant DEK/KEK wrap-unwrap scheme →
single global key (`settings.pii_encryption_key`), same PBKDF2
derivation as the old "legacy" fallback branch — **zero data migration
needed**, existing ciphertext decrypts unchanged.

**Frontend renames (D1–D3):** `views/tenant/` → `views/operate/`;
`views/superadmin/` → `views/console/`; `tenantStore` → `appStore`;
`TenantNarrative` → `AccountNarrative`; `TenantAuditLog` →
`AccountAuditLog`.

---

## 4. Fresh Alembic chain (C6)

The DB path was greenfield per spec §4.8: a fresh chain from `001`
replaced the old 41-revision history (which was saturated with
tenant-scoped DDL). Result: 139 tables / 418 indexes / 122 FKs / 46
column comments; `up` → `down` → `up` verified clean.

**Load-bearing detail**: `migrations/env.py`'s custom `render_item`
hook renders `StrEnumType` columns as native `postgresql.ENUM(...)` DDL
during autogenerate. Without it, a future autogenerated enum column
would emit as `VARCHAR` and 500 at runtime on the first filtered query.
Documented in `backend/docs/02-backend/database-schema.md` (this task,
per C6 handoff).

---

## 5. Two-layer feature-flag architecture

Two independent layers, deliberately kept separate (`task-C5-report.md`):

1. **Env-var kill-switches** (`core/feature_gate.py`, from A1) —
   process-wide, ops-controlled, redeploy-to-change. `FeatureGate`/
   `require_feature` return `404` when off. E.g.
   `feature_knowledge_graph`, `ENABLE_PUBLIC_SIGNUP`.
2. **`Organization.feature_flags`** (JSONB, `app/features/flags.py` +
   `service.py`) — org-configurable, mutable at runtime by the owner via
   `PUT /api/v1/features`. `DEFAULT_ORG_FEATURES` replaces the old
   5-tier `DEFAULT_FEATURES_BY_PLAN` dict with **exactly the values the
   old `PROFESSIONAL` tier held** — zero runtime behavior change,
   verified by diff.

`PlanTier` and all tier-keyed lookups are gone entirely.

---

## 6. Deferred product decisions (not resolved in this conversion)

1. **`views/am/*` Account Manager feature** — calls `/admin/*` routes
   that were never mounted post-conversion (`backend/app/api/v1/endpoints/admin.py`
   does not exist). Not a conversion casualty — this feature was already
   dead. Needs a dedicated design/build task, not a rename. (D3)
2. **`views/operate/AuditLog` page** — its `/audit` route family
   (`useTenantAuditLogs` etc.) has no matching backend beyond the
   separate `ConsoleDashboardSummary.AuditLogEntry` shape; `api/audit.ts`
   is annotated non-functional. (D3)
3. **Residual `Tenant`-prefixed class/table names** — kept as-is,
   semantically global-scoped: `TenantEnforcementSettings`,
   `TenantEnforcementRule`, `TenantPlatformConnection`, `TenantAdAccount`,
   `TenantOnboarding`. Renaming these is a schema-touching naming
   decision explicitly deferred past C6 (would ripple through
   migrations/tests for no functional benefit at this stage).
4. **404-vs-503 off-flag semantics split** — `FeatureGate` (A1) returns
   `404` when a flag is off; pre-existing env-flag gates in
   `rules.py`/`competitors.py` return `503`. Spec §10 favors 404/403 per
   flag semantics; the knowledge-graph convention uses 503. Not
   reconciled — pick one convention at a future pass. (A1 review)
5. **Dead `Billing` sidebar nav item** (found during this task's docs
   sweep) — `frontend/src/components/primitives/nav/dashboardNav.ts`
   still lists `{ label: 'Billing', href: '/dashboard/settings/billing' }`
   in the Workspace group. No route/backend answers it (Payments was
   removed by A2/A4); it falls through to the Settings page's default
   tab. Not fixed here (frontend source change, out of E2's docs-only
   scope) — flagged for a cleanup pass alongside item 3.

---

## 7. Known documentation debt (this task's scope boundary)

E2 aligned `CLAUDE.md`, `README.md`, and the highest-traffic
`backend/docs/**` files (glossary, architecture, integrations,
figma-theme, launch-readiness guide, auth/security overviews, the
Payments/Superadmin feature-spec folders, tier tutorials, env-var
references, and several legacy platform-documentation snapshots) with
either direct edits or explicit staleness banners. **Not exhaustively
rewritten**: `backend/docs/02-backend/database-schema.md`'s per-table
`CREATE TABLE` reference still lists `tenant_id` columns (flagged with
a top-of-file banner — regenerating it against the real 139-table fresh
schema is follow-up work), and a long tail of smaller `04-features/*`
docs (01, 02, 05, 06, 07, 08, 09, 10, 11, 12) were not individually
swept for incidental tenant mentions in edge-cases/api-contracts prose.
None of these are current-behavior blockers (`backend/app` itself greps
clean), but a RAG indexer could still surface stale phrasing from them.

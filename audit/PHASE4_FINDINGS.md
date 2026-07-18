# PHASE 4 — DATA ACCESS & INTEGRITY AUDIT
Audit date: 2026-07-18.

## Scope declared
Removed `tenant_id` read/write scopes and asymmetry; composite UNIQUE/index constraints that included `tenant_id`; leftover cross-tenant rows; ORM default scopes/global filters; FK/sequence integrity after the squashed migration; soft-delete filters. Healthy = every query correct for exactly one org, global uniqueness replacing tenant-scoped uniqueness, no orphan rows. Findings this phase: **3** (0 CRITICAL, 3 MEDIUM — all DEGRADED, all latent-but-real).

## Pivotal fact: the schema is GREENFIELD → the CRITICAL data-leak branch is N/A
- Initial migration `12a656044fcc` has `down_revision = None` (`…initial_schema_single_client.py:18`); it is the root of a 3-revision chain squashed at conversion.
- **Zero data-migration statements**: no `bulk_insert`, no `op.execute("INSERT…")`, no tenant-backfill `UPDATE` in any migration (grep = 0).
- Therefore there is **no pre-existing multi-tenant data** carried across the conversion. The Phase 4 CRITICAL concerns — "leftover rows from other tenants now visible = data leak", "count rows per former tenant_id", "existing data violates new global constraints", "sequence reset from tenant offsets" — are **all N/A by construction**. Any deployment starts from an empty schema and seeds one org (id=1). This is the single most important integrity fact in the audit and it is strongly positive.

## What is HEALTHY (evidence-backed)
- **Organization singleton is the correct model**: `id=1` fixed, DB-level `CheckConstraint("id = 1", name="ck_organization_singleton")` (`base_models.py:251`), fetched via `db.get(Organization, 1)` (`base_models.py:270`), raises if unseeded. This is the pattern the two failing singletons below should have copied.
- **`users.email_hash` global UNIQUE preserved** (`uq_user_email_hash`, migration:2827, model:364) — tenant-scoped `(tenant_id, email)` correctly collapsed to global email uniqueness; correct for one org.
- **Composite uniques correctly globalized** (dropping tenant_id is semantically right for one org, and greenfield means no existing row violates them): `uq_audience`/`uq_creative`/`uq_campaign_platform_external` = `(platform, external_id)`; `uq_daily_kpi_scope` = `(date, platform, account_id, campaign_id)`; `uq_campaign_metric_date` = `(campaign_id, date)`; CDP `(identifier_type, identifier_hash)`; CMS slug/name uniques.
- **Trust-gate rollup upserts correctly** by `(date, platform)` via `scalar_one_or_none` (`signal_health_rollup.py:244-285`), consumed cleanly by `quality/trust_layer_service.py:55-60` — no duplicate hazard on the trust-gate read path.
- **No ORM global tenant scope left behind**: no `with_loader_criteria` / `do_orm_execute` default-scope listener exists (`db/session.py` connect hook is a Postgres session setup, not a query filter). Nothing silently injects or requires tenant_id.
- **Soft-delete**: manual per-query `is_deleted == False` filtering (31 sites); pre-existing design (no global scope), unaffected by conversion.

## FINDINGS

```
FINDING-4-1
Feature:        FEAT-040 / FEAT-108 (Autopilot enforcement — emergency stop)
Status:         DEGRADED
Severity:       MEDIUM
Confidence:     HIGH (defect present; failure requires >1 settings row)
What is broken: enforcement_settings is treated as a singleton in code but has NO DB-level
                single-row guarantee. Model `models/autopilot.py:72` sets `__table_args__ = ()`
                — no CheckConstraint("id = 1"), no unique key (contrast Organization). Row
                creation is imperative "insert if none found" in TWO places (enforcer.py:271-284
                get_settings, and :355-360 update_settings "create if missing"), with a race
                window and no serialization. BOTH readers use unordered `.first()`:
                  - enforcer.py:230,344  `select(EnforcementSettingsDB)...scalars().first()`
                  - apply_actions_queue.py:1219  is_autopilot_frozen(): `select(
                    EnforcementSettings.autopilot_frozen)...scalars().first()`
Root cause:     Conversion dropped the tenant_id scope (and its per-tenant uniqueness) that
                previously made the read deterministic (`.where(tenant_id==X).first()`), and
                replaced it with NOTHING — no key at all. The "singleton" is now convention-only.
Blast radius:   SAFETY. If two rows ever persist (concurrent freeze toggles, or a read-path
                get_settings on an empty DB committed concurrently with another creator), the
                operator's emergency-stop write (autopilot_frozen=True / kill switch / default
                enforcement mode) can land on row A while is_autopilot_frozen() reads row B and
                returns False — automated ad-budget changes keep executing after an operator hit
                "Freeze". Silent. Paired issue (FINDING context): enforcement_rules carries a now-
                GLOBAL `uq_rule_id` (`models/autopilot.py:182`), so the same rule_id cannot coexist
                across two settings rows → IntegrityError aborting a settings update if #1 occurs.
Evidence:       models/autopilot.py:72 `__table_args__ = ()`; docstring literally says "(singleton)"
                with no constraint backing it. enforcer.py:271-284 + :355-360 dual insert paths.
                apply_actions_queue.py:1210-1220 docstring asserts "there is exactly one settings
                row" — an assumption the schema does not enforce.
Fix:            Add `CheckConstraint("id = 1")` (or a partial unique index `WHERE true`) and fetch
                by id=1 like Organization; make get_settings upsert-by-id=1, not insert-if-missing.
                Migration to collapse any existing dupes to one row before adding the constraint.
Confirm via:    Insert a 2nd enforcement_settings row; set autopilot_frozen=True on the higher id;
                call is_autopilot_frozen() → currently can return False (reads the other row).
```

```
FINDING-4-2
Feature:        FEAT-054 (Onboarding wizard state)
Status:         DEGRADED
Severity:       MEDIUM
Confidence:     HIGH (defect present; failure requires >1 onboarding row)
What is broken: organization_onboarding has the same convention-only singleton problem. Model
                `models/onboarding.py` id is plain autoincrement with only a non-unique status
                index — no fixed id, no unique constraint. get_or_create_onboarding()
                (onboarding.py:275-291) does `select(OrganizationOnboarding).limit(1)` +
                scalar_one_or_none then inserts on miss, and READ endpoints commit after calling it
                (GET /status :334, GET /check :776 both persist a row on first load). Reads use
                `.limit(1)` with no order_by.
Root cause:     Same as 4-1 — de-tenanting removed the per-tenant key without adding an id=1 guard;
                the table was renamed tenant_onboarding→organization_onboarding but not re-keyed.
Blast radius:   Two concurrent first-loads (multi-tab boot, or /status + /check racing before
                either commits) create two rows. Thereafter `.limit(1)` returns an arbitrary row:
                POST /business-profile writes step data to row A, GET /status reads row B →
                onboarding progress/current_step flaps; a completed onboarding can read back as
                un-started; approval/trust thresholds saved during onboarding land on the wrong row.
Evidence:       onboarding.py:279,728 `.limit(1)`; get-or-create inserts on miss; read endpoints
                commit. No unique/id=1 constraint in model or migration.
Fix:            Same as 4-1: id=1 CheckConstraint + fetch-by-id; make reads non-persisting (don't
                create in a GET), or upsert-by-id=1.
Confirm via:    Fire GET /onboarding/status and GET /onboarding/check concurrently on an empty DB →
                two rows; subsequent status reads become nondeterministic.
```

```
FINDING-4-3
Feature:        FEAT-164 (CRM integrations — HubSpot/Zoho/Pipedrive connection)
Status:         DEGRADED
Severity:       MEDIUM
Confidence:     HIGH
What is broken: crm_connections get-or-create keys on `provider` alone, but CRMConnection has NO
                UniqueConstraint on provider (`models/crm.py:162-165` — only Index
                ix_crm_connections_provider). The per-tenant uniqueness that used to key this was
                dropped without leaving a single-provider unique key. Lookups use
                `select(CRMConnection).where(provider==X).scalar_one_or_none()`
                (hubspot_client.py:792-798; same in zoho_client.py:870, pipedrive_client.py:656).
Root cause:     Conversion removed tenant scope + its unique constraint; get-or-create lookup key
                (provider) no longer matches any unique constraint, so nothing prevents 2 rows.
Blast radius:   Once two rows exist for one provider (re-run OAuth connect before first commit,
                reconnect after REVOKED, concurrent sync+status), every `_get_connection()`
                scalar_one_or_none() raises MultipleResultsFound → the connection-status endpoint
                and all sync/writeback for that provider 500 PERMANENTLY until a row is manually
                deleted. (Note: CRM sync tasks are also unregistered on the worker per Phase 6
                seed FEAT-119, so the live trigger is the endpoints, not beat.)
Evidence:       models/crm.py:162-165 __table_args__ lacks UniqueConstraint("provider").
                hubspot_client.py:800-814 inserts on miss.
Fix:            Add UniqueConstraint("provider") (single-org: one connection per provider) and
                convert get-or-create to an upsert / ON CONFLICT DO UPDATE on provider.
Confirm via:    Insert two crm_connections rows with provider='hubspot'; GET the HubSpot status
                endpoint → 500 MultipleResultsFound.
```

## Common root cause & remediation theme
All three are the **same conversion anti-pattern**: a table that was uniquely keyed by `tenant_id` (one row per tenant) had the tenant scope removed but was **not re-keyed to a single-org invariant**. The correct template already exists in this codebase — `Organization` (fixed `id=1` + `CheckConstraint("id = 1")` + `db.get(…, 1)`). Applying that template (id=1 guard + upsert-by-id, non-persisting reads) fixes 4-1/4-2/4-3 together. None is currently a guaranteed failure — each needs a duplicate row to exist first — but the schema no longer prevents that duplicate, which is exactly the latent-failure class this audit targets (works until a race, then silent for 4-1/4-2, hard-500 for 4-3).

## Cross-refs & N/A
- No composite-unique data violations possible (greenfield). No cross-tenant row leak (no such rows). No FK-to-deleted-Tenant dangling references (Tenant table never existed in this schema). No sequence-reset issue (fresh sequences).
- Category-3 aggregation mislabels: only the two already recorded in Phase 2 (`analytics.py:709 total_tenants=1` = N-1; `emq_service` totalTenants = FINDING-2-1). Sweep found no additional ones (`console_analytics`, `trust_layer` counts verified genuine).
- FINDING-4-3 blast radius intersects Phase 6 (FEAT-119 CRM tasks unregistered) and Phase 9 (integrations).

## Phase 4 summary
Structural integrity is **strong**: greenfield schema eliminates every data-leak/orphan-row concern, composite uniques correctly globalized, users/org keyed properly. The weakness is a repeated **singleton-without-a-constraint** pattern in three per-org state tables (enforcement settings, onboarding, CRM connection) — latent today, but the DB no longer enforces the one-row invariant the code assumes, and one of the three (enforcement emergency-stop) is safety-relevant. All DEGRADED/MEDIUM; fix is uniform.

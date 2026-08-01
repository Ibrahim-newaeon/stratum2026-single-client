# PHASE 12 — OBSERVABILITY, TESTS & CI
Audit date: 2026-07-18.

## Scope declared
Logs/dashboards/alerts keyed on a tenant dimension (silent blind spots); analytics/error-tracker tenant properties; test suites (multi-tenant tests converted vs deleted → coverage delta); fixtures/seeds; CircleCI-vs-GitHub-Actions duplication; fresh-install migration-from-zero. Findings: **2** (0 CRITICAL, 2 LOW). 2 observations.

## OBSERVABILITY — OPERATIONAL (clean)
- **No tenant metric labels/dimensions**: grep of `monitoring/` (Prometheus rules, Grafana) and `backend/app/monitoring` + `core` instrumentation for tenant/org labels = 0. Alerts key on real dimensions (decision/platform/severity), so no alert "matches nothing" → no silent monitoring blind spot. The Phase-2 alert-rule phrase "across multiple tenants" is annotation TEXT only (RESIDUE N-13), not a metric selector.
- **No tenant log fields**: `core/logging.py`, `middleware/request_logging.py`, `middleware/audit.py` bind no tenant (grep = 0). structlog context binds `user_id, role` only (auth_context.py:123).
- **CircleCI is an intentional no-op**, not a stale duplicate: `.circleci/config.yml` = `workflows: noop: jobs: []` with a header "ADs Growth System uses GitHub Actions… kept to prevent CircleCI errors… performs no actions." Dispositions Phase-0 watch-list #4.

## TESTS — OPERATIONAL (genuine conversion, not silent deletion) — the phase's key question
The audit's central concern ("CI green ≠ healthy if multi-tenant tests were DELETED rather than CONVERTED") is **answered positively**: the removals are deliberate, individually commented with `STRAT-SC-001` rationale, and security-relevant coverage was re-expressed, not lost.
- **Scale intact**: 290 test files, ~5,700 test functions (unit 181/~3,558; integration 108/~2,074). Not gutted.
- **Fixtures CONVERTED**: the old `test_tenant` factory → `organization` singleton fixture (conftest.py:282-291, upserts `Organization.id==1`, `ck_organization_singleton`); `authenticated_client`/`app`/`client` all documented as de-tenanted (conftest.py:186-261).
- **Tests PORTED (coverage preserved)**: `test_auth_mw_blacklist.py` (from `test_tenant_mw_blacklist.py` — same AUTH-001 enforcement vs new middleware); `test_pii_encryption.py` (supersedes `test_pii_keys.py`, adds `test_encrypt_pii_signature_has_no_tenant_param`); `test_global_uniqueness.py` (18 constraint pairs — User.email_hash, Campaign, slugs — re-proven GLOBAL with real `IntegrityError` negatives); `test_feature_gate.py`+`test_features_flags.py` (31 tests) re-create gating coverage for the new env+org-flag model.
- **Cross-tenant isolation tests DELETED — but justifiably**: `test_tenant_isolation.py`, `test_ws_tenant_isolation.py`, and ~20 inline `test_cross_tenant_forbidden`/`test_requires_tenant_match` cases were removed because a second tenant cannot exist post-conversion (`ck_organization_singleton`), so they could never regress-catch anything real. Every deletion site carries a `STRAT-SC-001` marker. This is inherent, not silent, coverage loss.
- **Billing/tier/subscription test modules deleted** with the removed feature (~11 modules) — correct.
- **No vacuous/toothless survivors**: no `assert total_tenants == 1`-style hollow tests; `/tenant-overview` test is a stale *name* on a real singleton-endpoint smoke test; uniqueness negatives keep their teeth.
- **Seeds converted**: `seed_owner.py` "replaces the old per-tenant seed_superadmin.py… no longer creates/looks up a tenants row"; creates Organization singleton + owner.

## MIGRATIONS / FRESH-INSTALL — OPERATIONAL
- **Fresh-install-from-zero is TESTED every run**: integration `conftest.py:524-571` `setup_test_database` does `DROP SCHEMA public CASCADE` → `CREATE SCHEMA` → **`command.upgrade(cfg, "head")`** via the real Alembic chain (explicitly replacing a former `create_all`). CI load-test job also runs `fix_alembic_version.py` → `alembic upgrade head` (ci.yml:652-654). The "migration from zero on a scratch DB" concern is positively resolved.
- **Chain is clean, single-head, linear**: `12a656044fcc`(down=None) → `b7e3f4a9c2d1` → `c8d2e5f7a1b3`.
- **Coverage floor**: real `fail_under = 74.0` ratchet (.coveragerc:257), enforced on combined unit+integration.

## FINDINGS

```
FINDING-12-1
Feature:        FEAT-205 (CI) / migration integrity
Status:         DEGRADED
Severity:       LOW
Confidence:     HIGH
What is broken: There is no explicit migration-drift / single-head / autogenerate-no-diff test.
                Model↔migration drift (a model column added without a migration) is only caught
                INDIRECTLY — the integration suite builds the schema from `alembic upgrade head`,
                so an ORM insert of a missing column would fail there, but a model change with no
                corresponding integration insert can slip through. Note `test_global_uniqueness.py`
                builds via `Base.metadata.create_all` (models), NOT migrations, so it validates
                model constraints but cannot catch migration drift.
Root cause:     No `alembic check` / `heads == 1` / model-vs-migration assertion in the suite.
Blast radius:   A future model change shipped without a migration could pass CI yet break a real
                `alembic upgrade head` deploy. Low today (chain is clean, greenfield), but the
                guardrail is absent.
Evidence:       grep test_migrations/test_schema_consistency = 0; conftest.py:569 upgrade-to-head;
                test_global_uniqueness.py uses create_all.
Fix:            Add a test: assert `len(alembic heads) == 1` and `alembic check` (autogenerate
                produces empty diff) against the models. Cheap, high-value regression guard.
Confirm via:    Run `alembic check` after a model edit with no migration → currently no test fails.
```

```
FINDING-12-2
Feature:        FEAT-006 / encryption test coverage
Status:         DEGRADED
Severity:       LOW
Confidence:     MEDIUM
What is broken: `test_pii_keys_provisioning.py` (per-tenant PII key provisioning) was deleted with
                no successor beyond single-key roundtrip tests. The surviving single global Fernet
                key derivation (security.py:_get_fernet_key, PBKDF2 over pii_encryption_key + static
                salt) has encrypt/decrypt roundtrip coverage (test_pii_encryption.py) but no explicit
                test of the key-derivation/config-validation path (e.g. prod-refuses-dev-default at
                config.py:554-556).
Root cause:     Per-tenant key provisioning genuinely vanished with the single-key model; the
                provisioning *concept* mostly disappeared, but the single-key config-guard path was
                not re-covered.
Blast radius:   Low — the derivation is simple and static; but a regression in the prod-key guard or
                salt would not be caught by a dedicated test.
Evidence:       orphaned test_pii_keys_provisioning.pyc, no .py successor; test_pii_encryption.py is
                roundtrip-only.
Fix:            Add a small test asserting `_get_fernet_key` derivation is stable and that prod
                rejects the dev-default key (config.py:554-556).
Confirm via:    Set the dev-default pii_encryption_key in a prod-like config → assert it raises.
```

## Observations (not findings)
- **OBS-12-a (doc drift)**: CLAUDE.md ("Alembic — fresh single-client chain (1 revision)") and the migrations/ CLAUDE note say **1 revision**; there are **3**. Stale doc. Dispositions Phase-1 seed #9; cross-ref FINDING-10-1 doc-truth theme.
- **OBS-12-b (coverage blind spots)**: `.coveragerc` `omit` list has 15 module lines excluded from the 74% denominator — includes dead code (`crm_sync_tasks` "absent from Celery include" = FINDING-6-2) and cut features (Salesforce/Pipedrive "cut from launch"). Documented/intentional, but those modules have no coverage floor; revisit when re-enabling.

## Phase-0/1 seeds dispositioned
- Watch-list #2 (`fix_alembic_version.py`) → benign pre-step widening `alembic_version` to VARCHAR(128); used by conftest + CI. Cleared.
- Watch-list #4 (CircleCI vs Actions) → CircleCI is a deliberate no-op stub. Cleared.
- Seed #9 (docs "1 revision" vs 3) → OBS-12-a.

## Phase 12 summary
Observability is **clean of tenant residue** (no metric labels, log fields, or alert dimensions → no silent blind spots), CircleCI is a deliberate no-op, and — the phase's crux — the test conversion is **genuine and well-documented, NOT a silent coverage deletion**: fixtures converted, security-critical middleware/PII/uniqueness tests ported or re-proven globally, and the only large deletions (cross-tenant isolation, billing) are inherently untestable/removed features, marked at every site. Fresh-install-from-zero is actively exercised (conftest + CI run `alembic upgrade head` on a scratch DB). Two LOW gaps: no explicit migration-drift assertion (12-1) and dropped PII-key-provisioning coverage without a single-key successor (12-2). CI-green here genuinely reflects health, not a masked regression.

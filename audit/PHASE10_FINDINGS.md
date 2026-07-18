# PHASE 10 — CONFIG, ENV & FEATURE FLAGS
Audit date: 2026-07-18.

## Scope declared
Env vars referencing tenancy; the two-layer flag system (env kill-switches + `Organization.feature_flags` JSONB) — do flags evaluate correctly for everyone or no one?; single-org settings-row resolution; the Phase-1 doc/code flag-default contradiction; IaC/DNS/TLS per-tenant residue. Findings: **1** (0 CRITICAL, 1 LOW — DEGRADED/docs).

## OPERATIONAL (evidence-backed)
- **No tenant env keys**: grep of `.env.example`, `.env.production.*`, `config.py`, deploy env → zero `DEFAULT_TENANT`/`TENANT_DOMAINS`/`TENANT_*` keys. Only hit is a `# per-tenant collectors` comment (deploy compose, already RESIDUE N-14). Env surface was purged (conversion commit 43eebd09).
- **Both flag layers resolve correctly against the singleton — flags gate for the single org, not "no one" and not a wrong row**:
  - *Env kill-switches* (`core/config.py` + `feature_gate.py`): process-wide booleans read from settings; `FeatureGate`/`require_feature` return 404 when off. Only `WHAT_IF_SIMULATOR`/`GDPR_TOOLS` are wired (both default-on).
  - *Org flags* (`Organization.feature_flags` JSONB): `FeatureFlagsService` fetches via **`get_organization(self.db)`** = `db.get(Organization, 1)` — the DB-constraint-enforced singleton (`CheckConstraint("id = 1")`) — then `merge_features(DEFAULT_ORG_FEATURES, org.feature_flags)` (service.py:39-41). Reads AND writes (service.py:68-98) go through the same singleton fetch. No `.first()`, no hardcoded row, no stale-row hazard (contrast the enforcement_settings/onboarding singletons in Phase 4, which lack the constraint — the org itself is correctly keyed).
- **Org flag defaults are sensible** (features/flags.py:48-60): signal_health/attribution_variance/ai_recommendations/anomaly_alerts/creative_fatigue/campaign_builder all `True`, autopilot_level `GUARDED_AUTO`, owner_profitability `False`. No flag defaults to a state that disables a core feature for everyone.
- **Public signup correctly locked**: `enable_public_signup` defaults `False` (invite-only, config.py:254) and is enforced at `auth.py:804`. Matches the invite-only design. Secure default.
- **IaC/DNS/TLS clean of per-tenant residue**: nginx `server_name` is fixed (localhost / beta.stratum-ai.com), no wildcard tenant vhost; CSP `connect-src` wildcards are third-party (`*.up.railway.app`, `*.sentry.io`), not tenant subdomains; `infrastructure/` holds only grafana/ + prometheus/ (no Terraform, no per-tenant DNS/cert provisioning); Caddy is single-site TLS. No per-tenant cert/vhost/subdomain provisioning to orphan.

## FINDING

```
FINDING-10-1
Feature:        FEAT-170 (env feature flags) — documentation truth
Status:         DEGRADED
Severity:       LOW
Confidence:     HIGH
What is broken: Docs state two feature flags default ON while the code defaults them OFF. An
                operator following the docs would expect Competitor Intelligence and Automation
                Rules enabled out of the box; they are disabled.
                  - Code: feature_competitor_intel=False (config.py:447),
                          feature_automation_rules=False (config.py:449)
                  - Docs: decisions-adr.md:344,346 show "= True";
                          env-vars.md:346,348 list default "true"
Root cause:     Docs not updated when the defaults were set to False during the conversion.
                Note: the CODE default is the CORRECT one — competitor_intel fabricates benchmark
                data via random (Phase 6 / celery_app.py:244-247 comment), so shipping it OFF is
                intentional and right. The DOCS are wrong, not the code.
Blast radius:   Operator confusion only; an admin may think these features are live and file a
                false bug, or enable competitor_intel expecting real data. No runtime effect.
Evidence:       config.py:447,449 vs decisions-adr.md:344,346 & env-vars.md:346,348 (quoted).
Fix:            Correct the two docs to default `false` (and note competitor_intel is shelved until
                a real data source exists). Cross-ref Phase 12 doc-truth sweep.
Confirm via:    Fresh env with no overrides → GET a competitor-intel route → 404 (feature off),
                contradicting the docs' "true".
```

## Phase-1 seed dispositioned
- **Seed #8** (docs claim flag defaults true, code false) → **FINDING-10-1** above. Resolved.

## Phase 10 summary
Config and feature-flags are **healthy and correctly de-tenanted**: no tenant env keys, no per-tenant IaC/DNS/TLS, public signup locked to invite-only by default, and — the key question — both flag layers evaluate correctly against the constraint-enforced singleton org (flags work for the single org, gate for neither "no one" nor a wrong row). The org-flag resolution via `get_organization(id=1)` is the *correct* singleton pattern that the Phase-4 settings tables (enforcement/onboarding) should emulate. The sole finding is cosmetic doc drift (10-1, LOW) where two flag defaults are documented as `true` but coded `false` — and the code is the correct side.

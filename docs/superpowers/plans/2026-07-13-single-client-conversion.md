# Single-Client Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the multi-tenant Stratum AI codebase in-place to the Single-Client edition per `STRATUM_AI_SINGLE_CLIENT_REBUILD_PROMPT_v2.1_FINAL.md` — remove exactly the §0.1 removal ledger (billing/commercial packaging + multi-tenant partitioning), preserve everything else.

**Architecture:** Phased, always-green refactor on branch `feature/STRAT-SC-001-single-client-conversion`. Phase A removes billing (Stripe/tiers/editions/licensing). Phase B renames `superadmin`→`owner`. Phase C removes backend tenancy (Tenant→Organization singleton, middleware, per-tenant PII keys, key de-namespacing, fresh Alembic chain). Phase D removes frontend tenancy (TenantLayout twin, tenantStore→appStore, X-Tenant-ID). Phase E adds the CI residue gate and final validation. Each task ends with the affected test suite green and a commit.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic + Celery/Redis + pytest; React 19 + Vite + TS + Zustand + TanStack Query + Vitest/Playwright.

## Global Constraints

- Working dir: `C:\Users\Vip\Desktop\Stratum-AI-Final-Single Client\Stratum-AI-Final-Single Client` (paths below are repo-relative). Branch: `feature/STRAT-SC-001-single-client-conversion`.
- **Removal ledger is exhaustive** — if a construct seems tenant/billing-shaped but is not in §0.1 of the spec, do NOT delete it; raise for review.
- Every model/migration line where uniqueness scope changed carries the inline comment `# was tenant-scoped; now global`.
- Type hints on all functions; Pydantic for all API I/O; async/await for I/O; `datetime.now(timezone.utc)` never `utcnow()`; `secrets` for tokens; `hmac.compare_digest` for comparisons; Fernet-encrypt PII; structlog JSON.
- Never reintroduce `tenant_id`, tenant headers, Stripe, or tier gating.
- Conventional commits: `refactor|feat|fix|test|docs(scope): message [STRAT-SC-001]`.
- Backend test commands run from `backend/`: `python -m pytest tests/unit -x -q` (unit), `python -m pytest tests/integration -x -q` (integration). Frontend from `frontend/`: `npx vitest run`, `npx tsc --noEmit`.
- Acceptance greps use `git grep -I` (skip binaries). Historical artifacts are excluded via pathspecs, never edited: `':!*.md' ':!*.html' ':!*.txt' ':!*.xlsx' ':!*.zip' ':!datasets' ':!audit' ':!superads-dashboard' ':!*.csv' ':!*.json.lock'`. Call this exclusion set `$EXCL` below.
- DB path is **greenfield** (spec §4.8 default): fresh Alembic chain from 001. The §12 live-DB conversion track is explicitly out of scope for this plan.

---

## Phase A — Billing removal (ledger A)

### Task A1: Backend — decouple tier gating from feature flags

The tier system is dual-purpose: `core/feature_gate.py` holds both env-driven `FeatureGate` (KEEP) and tier/402 machinery (REMOVE). Non-billing endpoints import tier symbols and must be decoupled before deletion.

**Files:**
- Modify: `backend/app/core/feature_gate.py` (keep `FeatureGate` + `require_feature`; delete `TierGate` class ~line 271, `require_tier` ~line 442, all `HTTP_402_PAYMENT_REQUIRED` raises at lines 246/313/486, `settings.subscription_tier` resolution ~line 101, `request.state.subscription_tier` caching)
- Modify: `backend/app/core/feature_gate.py` — move the `Feature` enum from `backend/app/core/tiers.py:33` into this file (env-flag features only; drop tier-mapping members)
- Delete: `backend/app/core/tiers.py`, `backend/app/core/subscription.py`
- Modify call sites (replace `TierGate`/`require_tier`/`check_tenant_limit`/`LimitChecker`/`SubscriptionTier` usage with plain `FeatureGate`/no-op removal): `backend/app/api/v1/endpoints/cdp.py`, `backend/app/api/v1/endpoints/autopilot_enforcement.py`, `backend/app/api/v1/endpoints/oauth.py`, `backend/app/api/v1/endpoints/users.py`, `backend/app/api/v1/endpoints/audience_sync.py`, `backend/app/services/embed_widgets/` (imports `SubscriptionTier`), `backend/app/api/v1/__init__.py:81` (`from app.core.tiers import Feature` → `from app.core.feature_gate import Feature`)
- Test: existing suites under `backend/tests/unit/` that cover feature gating (locate: `git grep -l "feature_gate\|FeatureGate" backend/tests`); delete tier-specific tests (`git grep -l "TierGate\|require_tier\|SubscriptionTier\|subscription" backend/tests`)

**Interfaces:**
- Produces: `app.core.feature_gate.Feature` (enum), `FeatureGate(feature: Feature)` dependency, `require_feature(feature)` decorator — the ONLY gating primitives after this task. All later tasks import `Feature` from `app.core.feature_gate`.

- [ ] **Step 1: Build the worklist** — `git grep -n "TierGate\|require_tier\|SubscriptionTier\|check_tenant_limit\|LimitChecker\|core.tiers\|core.subscription\|subscription_tier" -- backend/app backend/tests` and save output to scratch. Every hit must be resolved in this task (app code) or Task A2/A3 (billing endpoints/services being deleted whole).
- [ ] **Step 2: Move `Feature` enum** into `feature_gate.py`, keeping member names used by routers (verify against `git grep -n "Feature\." backend/app/api`). Delete tier-limit members only if unreferenced after the sweep.
- [ ] **Step 3: Strip tier machinery from `feature_gate.py`** — remove `TierGate`, `require_tier`, 402 raises, `get_tier_limits` imports. `FeatureGate.__call__` now only checks env-driven flags; when a feature is off raise `HTTPException(status_code=404)` (match existing off-flag semantics — check current behavior first and preserve it).
- [ ] **Step 4: Fix the five endpoint call sites + embed_widgets services.** Where a route used `Depends(TierGate(...))` or `require_tier`, delete the dependency (the route becomes available to all authenticated users). Where it used `check_tenant_limit`/`LimitChecker` (resource caps), delete the check and its error branch.
- [ ] **Step 5: Delete `core/tiers.py` and `core/subscription.py`**, delete tier tests found in Step 1.
- [ ] **Step 6: Verify** — `git grep -n "TierGate\|require_tier\|SubscriptionTier\|core\.tiers\|core\.subscription" -- backend/app` returns empty (billing endpoints deleted in A2 may still match — they are next). Run `cd backend && python -m pytest tests/unit -x -q`.
- [ ] **Step 7: Commit** — `refactor(billing): decouple tier gating; FeatureGate is the only gate [STRAT-SC-001]`

### Task A2: Backend — remove billing endpoints, stripe service, config, beat tasks

**Files:**
- Delete: `backend/app/api/v1/endpoints/subscription.py`, `backend/app/api/v1/endpoints/tier.py`, `backend/app/api/v1/endpoints/payments.py`, `backend/app/api/v1/endpoints/stripe_webhook.py`, `backend/app/services/stripe_service.py`, `backend/app/workers/tasks/billing.py`
- Modify: `backend/app/api/v1/__init__.py` — remove imports (lines ~56, 67, 68, 73) and `include_router` calls (~439, 453, 459, 466)
- Modify: `backend/app/core/config.py:363-381` — delete the 6 `stripe_*` settings
- Modify: `backend/app/middleware/security.py:91-110` — remove `api.stripe.com`, `js.stripe.com`, `hooks.stripe.com` CSP entries (both duplicated blocks)
- Modify: `backend/app/middleware/csrf.py` — remove stripe-webhook path exemption
- Modify: `backend/app/workers/celery_app.py:123,129` — remove `calculate-cost-allocation` and `calculate-usage-rollup` beat entries; `backend/app/workers/tasks/__init__.py` — remove billing imports; check legacy `backend/app/workers/tasks.py` for billing remnants
- Modify: `backend/requirements.txt:90` + `backend/requirements-prod.txt` — remove `stripe>=15.3.0`; `backend/mypy.ini`, `backend/.coveragerc` — remove stripe entries
- Modify: `backend/.env.example:171-176`, root `.env.example` — remove `STRIPE_*` vars
- Test: delete billing test files (`git grep -il "stripe\|payments\|subscription" backend/tests` — review each; delete only billing-purposed files, fix incidental references in others)

- [ ] **Step 1:** Delete the six files. Remove router imports/registrations from `api/v1/__init__.py`.
- [ ] **Step 2:** Sweep config/CSP/CSRF/celery/requirements/env per the file list. In `middleware/tenant.py` the stripe-webhook path appears in public-endpoint exemptions — leave that file alone (whole file is removed in C3; removing one line now breaks nothing but creates noise).
- [ ] **Step 3:** Test sweep. Then `cd backend && python -m pytest tests/unit -x -q && python -m pytest tests/integration -x -q`.
- [ ] **Step 4:** Verify app boots: `cd backend && python -c "from app.main import app; print('ok')"`.
- [ ] **Step 5:** Commit — `refactor(billing): remove stripe endpoints, service, config, beat tasks [STRAT-SC-001]`

### Task A3: Backend — remove licensing, provisioning, limits, editions

**Files:**
- Delete: `backend/app/services/tenant/` (entire package: `licensing.py`, `limits.py`, `provisioning.py`, `__init__.py`)
- Delete: `editions/` (entire directory: build.sh, build.bat, README.md, exclude.txt, starter/, professional/, enterprise/)
- Test: delete `backend/tests/unit/test_licensing_pure.py`; fix `backend/tests/unit/test_secrets_at_rest.py` (references `LICENSE_SIGNING_SECRET` — remove that assertion only, keep the rest)

- [ ] **Step 1:** `git grep -ln "services.tenant\|services\.tenant\|LicenseValidationService\|get_license_service\|TenantProvisioningService\|TenantLimitService" -- backend/app backend/tests` — resolve every importer (most were fixed in A1; `superadmin.py`/`tenants.py` importers get deleted in Phase C — if they import these, stub the import out now with a deletion of the endpoint's licensing routes, or defer by keeping the file until C; prefer: delete the importing routes now).
- [ ] **Step 2:** Delete `backend/app/services/tenant/` and `editions/`.
- [ ] **Step 3:** Tests + boot check as in A2 Steps 3–4.
- [ ] **Step 4:** Commit — `refactor(billing): remove licensing, provisioning, limits, editions [STRAT-SC-001]`

### Task A4: Frontend — remove Stripe, tiers, checkout, pricing, 402 flow

**Files:**
- Delete: `frontend/src/contexts/TierContext.tsx` + `TierContext.test.tsx`, `frontend/src/components/billing/` (UpgradePromptProvider.tsx, OutcomeNudge.tsx, TrialBanner.tsx), `frontend/src/api/payments.ts`, `frontend/src/api/tier.ts`, `frontend/src/api/subscription.ts`, `frontend/src/views/checkout/` (3 files), `frontend/src/views/dashboard/Plans.tsx`, `frontend/src/views/plans/TierLandingPage.tsx`, `frontend/src/views/pages/Pricing.tsx`, `frontend/src/views/cms/CMSLandingPricing.tsx`, `frontend/src/components/landing/Pricing.tsx`, `frontend/src/components/landing/tier/` (5 files), `frontend/src/config/tierLandingContent.ts`, `frontend/src/views/superadmin/Billing.tsx`
- Modify: `frontend/src/App.tsx` — remove `UpgradePromptProvider` import (line ~12) + wrapper (~293, ~2150); remove lazy imports + routes for Plans, CheckoutPage/Success/Cancel, TierLandingPage, PricingPage, CMSLandingPricing, SuperAdminBilling (route lines ~499, 540, 559, 562, 861–890, 929, 933, 1958)
- Modify: `frontend/src/api/client.ts:168-178` — delete the 402 → `stratum:upgrade-required` dispatch block (keep 401 refresh mutex untouched)
- Modify: `frontend/package.json` — remove `@stripe/react-stripe-js`, `@stripe/stripe-js`
- Modify: consumers of removed pieces: `frontend/src/views/Settings.tsx` (billing section/links), `frontend/src/components/changelog/WhatsNew.tsx`, `frontend/src/components/common/ErrorScreen.tsx`, `frontend/src/views/APIKeys.tsx`, `frontend/src/api/hooks/useSuperAdmin.ts` (billing fields), `frontend/src/components/landing/*` importers of Pricing, `frontend/src/views/superadmin/TenantsList.tsx`/`TenantProfile.tsx` (plan/MRR columns — these views die in Phase D; only fix if they import deleted modules), `frontend/src/views/tenant/ConnectPlatforms.tsx`
- Modify: `frontend/nginx.conf`, `frontend/nginx.railway.conf` — remove Stripe CSP entries; `vercel.json` — remove `/pricing` rewrite (line ~22)
- Test: `frontend/src/views/dashboard/Overview.test.tsx` (references upgrade event — remove that case); delete tests co-located with deleted files

- [ ] **Step 1:** Build worklist: `git grep -ln "stripe\|TierContext\|useTier\|UpgradePrompt\|upgrade-required\|/checkout\|/pricing\|/plans" -- frontend/src` (case-insensitive second pass). Note: `pinstripe` CSS matches in `components/ui/progress.tsx` / `data-table.tsx` are false positives — rename that CSS class to `pinline` so the Phase E residue gate passes.
- [ ] **Step 2:** Delete the files listed; sweep App.tsx routes/providers and client.ts 402 block.
- [ ] **Step 3:** `cd frontend && npm uninstall @stripe/react-stripe-js @stripe/stripe-js` (regenerates package-lock.json).
- [ ] **Step 4:** Fix consumers until `npx tsc --noEmit` is clean; `npx vitest run` green.
- [ ] **Step 5:** Verify: `git grep -in "stripe" -- frontend/src frontend/package.json` returns empty.
- [ ] **Step 6:** Commit — `refactor(billing): remove stripe, tiers, checkout, pricing from frontend [STRAT-SC-001]`

---

## Phase B — `superadmin` → `owner` rename (ledger B, same semantics)

### Task B1: Backend rename

**Files:**
- Modify: `backend/app/base_models.py:49` — `UserRole.SUPERADMIN = "superadmin"` → `UserRole.OWNER = "owner"`
- Modify: `backend/app/auth/permissions.py` — `ROLE_PERMISSIONS["superadmin"]`→`["owner"]` (129), `ROLE_HIERARCHY[OWNER]=100` (420), `_ROLE_SCOPE[OWNER]="global"` (447), `is_superadmin_role()`→`is_owner_role()` (585), `require_super_admin`→`require_owner` (693), RBAC/SIDEBAR maps; drop `TENANT_*` and `BILLING_*` members of the `Permission` enum and their `ROLE_PERMISSIONS` references
- Rename: `backend/app/api/v1/endpoints/superadmin.py`→`console.py` (router prefix `/superadmin`→`/console`), `superadmin_analytics.py`→`console_analytics.py` (prefix `/superadmin/analytics`→`/console/analytics`); update `backend/app/api/v1/__init__.py` (lines ~79, 174, 217, 224, 245 — incl. `launch_readiness` mount `/superadmin/launch-readiness`→`/console/launch-readiness`)
- Rename: `backend/scripts/seed_superadmin.py`→`seed_owner.py` (role string inside)
- Modify: every `"superadmin"` string: `git grep -ln "superadmin\|super_admin\|SUPERADMIN" -- backend/app backend/scripts` (touches `middleware/tenant.py`, `tenancy/*` — these die in C; update only files that survive)
- Test: rename/update tests referencing the role (`git grep -l superadmin backend/tests`)

- [ ] **Step 1:** Write a failing unit test first in `backend/tests/unit/test_owner_role.py`:

```python
from app.base_models import UserRole
from app.auth.permissions import ROLE_HIERARCHY, require_owner  # noqa: F401


def test_owner_role_replaces_superadmin() -> None:
    assert UserRole.OWNER.value == "owner"
    assert not hasattr(UserRole, "SUPERADMIN")
    assert ROLE_HIERARCHY[UserRole.OWNER] == 100
```

- [ ] **Step 2:** Run it: `python -m pytest tests/unit/test_owner_role.py -x -q` — FAILS (no OWNER attr).
- [ ] **Step 3:** Apply the rename sweep (enum, permissions, endpoint files, seed script, api __init__). Keep the level-100 semantics and scoping bypass exactly; only names change. Skip `middleware/tenant.py` + `app/tenancy/` (deleted in Phase C).
- [ ] **Step 4:** Full backend suite green; new test passes.
- [ ] **Step 5:** Commit — `refactor(auth): rename superadmin role to owner; superadmin endpoints to console [STRAT-SC-001]`

### Task B2: Frontend rename

**Files:**
- Modify: `frontend/src/stores/tenantStore.ts` (role union `'superadmin'`→`'owner'`, `isSuperAdmin`→`isOwner`, `isSuperAdminMode`→`isOwnerMode`, `superAdminBypass`→`ownerBypass` — full store rename to `appStore` happens in D2; here only role strings/helpers), `frontend/src/contexts/AuthContext.tsx` (role union + demo creds), `frontend/src/components/auth/ProtectedRoute.tsx` (`requiredRole="superadmin"`→`"owner"`), `frontend/src/App.tsx` (`requiredRole` at `/console` route ~line 1894), `frontend/src/components/primitives/nav/dashboardNav.ts:75-117` (SIDEBAR_VISIBILITY key), `frontend/src/components/primitives/nav/consoleNav.ts`, `frontend/src/api/hooks.ts`, `frontend/src/api/featureFlags.ts`, `frontend/src/api/superadminAnalytics.ts`→rename `consoleAnalytics.ts` (+ endpoint paths `/superadmin/*`→`/console/*`), `frontend/src/api/hooks/useSuperAdmin.ts`→`useConsole.ts` (+ paths)
- Modify: `frontend/src/views/SuperadminDashboard.tsx`→`views/console/ConsoleDashboard.tsx`; `frontend/src/views/superadmin/*`→ merge into `frontend/src/views/console/` (Audit, Benchmarks, ControlTower, LaunchReadiness, System, Users; TenantsList/TenantProfile deferred to D3 where they're deleted)
- Test: update all vitest files matching `git grep -il superadmin frontend/src`

- [ ] **Step 1:** Sweep with worklist `git grep -in "superadmin\|super_admin\|SuperAdmin" -- frontend/src` — every hit either renamed to owner/console or (TenantsList/TenantProfile/Billing references) marked for D3.
- [ ] **Step 2:** API paths: all `/superadmin/*` calls become `/console/*` (must land in the same PR window as B1 — backend prefixes changed).
- [ ] **Step 3:** `npx tsc --noEmit` + `npx vitest run` green.
- [ ] **Step 4:** Commit — `refactor(auth): rename superadmin to owner across frontend; /console API paths [STRAT-SC-001]`

---

## Phase C — Backend tenancy removal (ledger B)

> Order inside C matters: C1 (models) breaks everything downstream until C2–C5 complete, so C1→C5 land as ONE PR with per-task commits; the suite is only required fully green again at end of C6. Run targeted module tests at each step.

### Task C1: `Organization` singleton + strip `tenant_id` from all models

**Files:**
- Modify: `backend/app/db/base.py:138` — delete `TenantMixin` (keep `TimestampMixin`:106, `SoftDeleteMixin`:122, `Base`:80)
- Modify: `backend/app/base_models.py` — delete `Tenant` (line 246) and `UserTenantMembership` (491); add `Organization` singleton; remove `TenantMixin` from 14 classes; remove `AuditLog.tenant_id` plain column (967); remove `stripe_customer_id`/plan/billing/limit columns that lived on Tenant (die with the class); rescope unique constraints (see table)
- Modify: all 22 `tenant_id`-bearing modules under `backend/app/models/`: attribution, audience_sync, audit_services, autopilot, campaign_builder, capi_delivery, cdp, client, crm, drip, embed_widgets, emq_playbook, launch_readiness, newsletter, onboarding, pacing, profit, push, reporting, settings, trust_layer (+ clients in client.py) — delete `tenant_id` columns/FKs/indexes/relationships, rescope constraints
- Delete: `backend/app/models/encryption.py` (`TenantEncryptionKey`) — per-tenant PII keys, ledger B
- Test: `backend/tests/unit/test_global_uniqueness.py` (new)

**Interfaces:**
- Produces: `app.base_models.Organization` — singleton model consumed by C2 (trust gate), C4 (workers), endpoints:

```python
class Organization(Base, TimestampMixin):
    """Singleton org row (id=1): identity, branding, thresholds, enforcement, onboarding."""

    __tablename__ = "organization"
    __table_args__ = (CheckConstraint("id = 1", name="ck_organization_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    branding: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # trust thresholds live here
    feature_flags: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    enforcement_mode: Mapped[str] = mapped_column(String(20), default="advisory", nullable=False)
    onboarding_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

  plus async helper in the same file:

```python
async def get_organization(db: AsyncSession) -> "Organization":
    """Fetch the singleton org row (id=1). Raises if seeding never ran."""
    org = await db.get(Organization, 1)
    if org is None:
        raise RuntimeError("Organization singleton missing — run seed_owner")
    return org
```

**§4.9 constraint conversion table (every line gets `# was tenant-scoped; now global`):**

| File:line (old) | Old constraint | New |
|---|---|---|
| base_models.py:481 | UNIQUE(tenant_id, email_hash) | UNIQUE(email_hash) |
| base_models.py:637 | uq_campaign_platform_external(tenant_id, platform, external_id) | UNIQUE(platform, external_id) |
| base_models.py:958 | UNIQUE(tenant_id, domain) | UNIQUE(domain) |
| base_models.py:524 | UNIQUE(user_id, tenant_id) | (table deleted) |
| models/audit_services.py:604 | UNIQUE(tenant_id, platform, external_id) | UNIQUE(platform, external_id) |
| models/audit_services.py:1000 | UNIQUE(tenant_id, platform, external_id) | UNIQUE(platform, external_id) |
| models/audit_services.py:1174 | UNIQUE(tenant_id, cohort_month) | UNIQUE(cohort_month) |
| models/autopilot.py:199 | UNIQUE(tenant_id, rule_id) | UNIQUE(rule_id) |
| models/campaign_builder.py:147 | UNIQUE(tenant_id, platform) | UNIQUE(platform) |
| models/cdp.py:775 | UNIQUE(tenant_id, profile_id) | UNIQUE(profile_id) |
| models/cdp.py:887 | UNIQUE(tenant_id, slug) | UNIQUE(slug) |
| models/cdp.py:1027 | UNIQUE(tenant_id, name) | UNIQUE(name) |
| models/cdp.py:1116 | UNIQUE(tenant_id, slug) | UNIQUE(slug) |
| models/client.py:130 | UNIQUE(tenant_id, slug) | UNIQUE(slug) |
| models/emq_playbook.py:47 | UNIQUE(tenant_id, item_key) | UNIQUE(item_key) |
| models/profit.py:142 | UNIQUE(tenant_id, sku) | UNIQUE(sku) |
| models/reporting.py:194 | UNIQUE(tenant_id, name) | UNIQUE(name) |
| models/reporting.py:559 | UNIQUE(tenant_id, channel, name) | UNIQUE(channel, name) |

Composite indexes that led with tenant_id drop the prefix (e.g. `ix_campaigns_tenant_status`→`ix_campaigns_status`). API duplicate contract: 409 for API-created resources, 422 for validation-layer catches — match each endpoint's existing conflict handling.

- [ ] **Step 1: Write the failing uniqueness tests** — `backend/tests/unit/test_global_uniqueness.py`. One positive+negative pair per converted constraint; template (uses existing async-session test fixtures from `tests/conftest.py` — reuse the pattern in current model tests):

```python
import pytest
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio
async def test_user_email_hash_globally_unique(db_session) -> None:
    # was tenant-scoped; now global
    u1 = make_user(email="dup@example.com")
    db_session.add(u1)
    await db_session.commit()          # positive: first insert succeeds
    u2 = make_user(email="dup@example.com")
    db_session.add(u2)
    with pytest.raises(IntegrityError):  # negative: global duplicate rejected
        await db_session.commit()
```

  Repeat for: campaigns(platform, external_id), cdp segment slug, cdp funnel slug, cdp trait name, clients slug, products sku, report template name, delivery config (channel,name), autopilot rule_id, platform connection platform, emq item_key, benchmark domain, audit_services ×3. Helper factories go at top of the test file with minimal required fields (copy column requirements from each model).
- [ ] **Step 2:** Run → fails (models still tenant-scoped / fixtures inject tenant_id).
- [ ] **Step 3:** Apply model changes: delete `TenantMixin` from `db/base.py`; rewrite `base_models.py` (Organization added, Tenant/UserTenantMembership gone, 14 classes de-tenanted, constraints rescoped w/ comment); sweep the 22 model modules (delete `tenant_id` mapped_columns, FK/index/relationship references, rescope per table); delete `models/encryption.py` and its export in any models `__init__`.
- [ ] **Step 4:** `python -c "from app import base_models; import app.models"` imports clean; uniqueness tests pass against a fresh test schema.
- [ ] **Step 5:** Commit — `refactor(models): Organization singleton; drop Tenant/tenant_id; global uniqueness per spec §4.9 [STRAT-SC-001]`

### Task C2: Auth middleware replaces TenantMiddleware; tenancy package + tenant endpoints removed

**Files:**
- Create: `backend/app/middleware/auth_context.py` — `AuthContextMiddleware`, preserving from `middleware/tenant.py`: `PUBLIC_ENDPOINTS` set (line 25) + `_is_public_endpoint` prefixes (191), JWT decode → `request.state.user_id/role/cms_role`, AUTH-001 token-type rejection + Redis blacklist check (88–98) **failing open if Redis is down but still rejecting non-`access` types**. Dropped: all tenant extraction, `X-Tenant-ID`, subdomain hook, `request.state.tenant_id/is_superadmin`.
- Delete: `backend/app/middleware/tenant.py`, `backend/app/tenancy/` (context.py, deps.py, __init__.py)
- Delete: `backend/app/api/v1/endpoints/tenants.py`, `backend/app/api/v1/endpoints/tenant_dashboard.py`; merge any dashboard-only routes from tenant_dashboard into `endpoints/dashboard.py` first (spec: "dashboard endpoints merge into dashboard") — diff route lists before deleting
- Modify: `backend/app/main.py:411` — swap `TenantMiddleware`→`AuthContextMiddleware` (same position: CORS→timing→security→audit→ratelimit→gzip→exception order per spec §4.6); remove `X-Tenant-ID` from CORS allow-list (main.py:458)
- Modify: `backend/app/api/v1/__init__.py` — remove tenants (100) + tenant_dashboard (238) registrations; de-prefix self-prefixed routers: `endpoints/autopilot.py` `/tenant/{tenant_id}/autopilot`→`/autopilot`, `endpoints/autopilot_enforcement.py` →`/autopilot/enforcement`, `endpoints/feature_flags.py` `/tenant/{tenant_id}`→`` + `/superadmin`→`/console`
- Modify: `backend/app/auth/deps.py:248` — delete `require_tenant_id`; `backend/app/core/security.py` — remove `tenant_id` claim from token creation/validation
- Test: port `backend/tests/unit/test_tenant_mw_blacklist.py`→`test_auth_mw_blacklist.py` (same assertions minus tenant); delete `test_tenant_context_dep.py`, integration `test_tenants_api.py`, `test_auth_tenants_api.py`, `test_tenant_dashboard_api.py`, `test_tenant_isolation.py`, `test_tenant_settings_api.py`

- [ ] **Step 1: Port the blacklist tests first** (failing against the not-yet-existing middleware):

```python
# test_auth_mw_blacklist.py — key cases to preserve verbatim from the tenant version:
# 1. revoked access token -> 401
# 2. refresh-type token on API route -> 401 even when Redis is down
# 3. Redis down + valid access token -> request passes (fail-open)
# 4. public endpoint -> no auth required
```

- [ ] **Step 2:** Write `AuthContextMiddleware` (copy tenant.py, excise tenant logic); tests pass.
- [ ] **Step 3:** Route merge audit: list `tenant_dashboard.py` routes vs `dashboard.py`; move unique ones across with `require_tenant_id`→current-user pattern. Delete the two endpoint files; fix `api/v1/__init__.py`; de-prefix autopilot/feature_flags routers.
- [ ] **Step 4:** JWT: remove tenant claim; run auth unit tests.
- [ ] **Step 5:** Commit — `refactor(auth): AuthContextMiddleware replaces TenantMiddleware; drop tenancy package + tenant endpoints [STRAT-SC-001]`

### Task C3: Endpoint + service `tenant_id` sweep (the monster — worklist-driven)

**Files:** every remaining `tenant_id`-bearing file under `backend/app/api/`, `backend/app/services/`, `backend/app/analytics/`, `backend/app/autopilot/`, `backend/app/stratum/`, `backend/app/quality/`, `backend/app/schemas/`. Heaviest (from survey): `endpoints/cdp.py` (232), `endpoints/dashboard.py` (131), `services/knowledge_graph/*` (~183), `autopilot/enforcer.py` (71), `endpoints/integrations.py` (63), `endpoints/audit_services.py` (63), `endpoints/campaign_builder.py` (57), `endpoints/whatsapp.py` (45), `endpoints/emq_v2.py` (42), `endpoints/compliance.py` (41), `models`-adjacent schemas.

**Mechanical recipe (apply per file, in this order):**
1. Function signatures: drop `tenant_id: int` params; queries drop `.where(X.tenant_id == tenant_id)` / `filter_by(tenant_id=...)`.
2. Object constructions drop `tenant_id=...` kwargs.
3. `require_tenant_id(...)` / `request.state.tenant_id` reads → deleted (auth still via `get_current_user`).
4. Brand scoping (`client_id` / `ClientAssignment`) is NOT tenant scoping — keep untouched.
5. `TrustGateConfig.from_tenant_settings` (stratum/core/trust_gate.py:80) → rename `from_org_settings`, same body/signature; update call site `endpoints/trust_layer.py:419` to pass `(await get_organization(db)).settings`.

- [ ] **Step 1:** Generate the worklist: `git grep -c "tenant_id" -- backend/app | sort -t: -k2 -rn > scratch/worklist.txt`. Work top-down; after each directory run that module's tests (`python -m pytest tests/unit -k <module> -q`).
- [ ] **Step 2:** `endpoints/` sweep (43+ files).
- [ ] **Step 3:** `services/` sweep (incl. knowledge_graph trio, sync orchestrator, capi, cdp, crm, reporting scheduler/delivery `self.tenant_id`).
- [ ] **Step 4:** `analytics/logic/`, `autopilot/` (service.py, enforcer.py), `stratum/` (trust gate rename, adapters, workers), `quality/trust_layer_service.py`, `schemas/`.
- [ ] **Step 5:** Rename test `test_trust_gate_per_tenant_config.py`→`test_trust_gate_org_config.py`, update to `from_org_settings`; fix `test_emq_gating_and_tenant_scoping.py`, `test_emq_per_tenant_weights.py` (keep EMQ-weight logic, re-scope to org settings), `test_ws_tenant_isolation.py` (deleted — WS rooms de-tenanted in C4), `test_exceptions_tenant_context.py` (deleted).
- [ ] **Step 6:** Acceptance: `git grep -n "tenant_id" -- backend/app ':!backend/app/workers' ':!backend/app/tasks' ':!backend/app/core'` returns empty (workers/core covered by C4).
- [ ] **Step 7:** Commit — `refactor(api,services): remove tenant_id threading across endpoints and services [STRAT-SC-001]`

### Task C4: PII single key, workers de-fan-out, metrics + key de-namespacing

**Files:**
- Delete: `backend/app/core/pii_keys.py` (per-tenant DEK envelope machinery)
- Modify: `backend/app/core/security.py:204,229` — `encrypt_pii(plaintext)` / `decrypt_pii(ciphertext)` drop the `tenant_id` param; single Fernet key from `settings.pii_encryption_key` (the existing legacy/global path becomes the only path). `backend/app/db/types.py:19` `EncryptedString` already calls without tenant_id — verify unchanged. Remove `initialize_pii_keys`/`load_all_tenant_deks` from `main.py` lifespan; replace with a startup assert that the key loads.
- Create: `backend/docs/security/pii-key-rotation.md` — documented rotation runbook (spec §0.1): generate new Fernet key → run `scripts/rotate_pii_key.py` (decrypt-all/re-encrypt in batched transactions with checkpoint) → swap `PII_ENCRYPTION_KEY` → restart. Write the runbook; the rotation script itself is listed as a follow-up item in the runbook (not built here — YAGNI until first rotation).
- Modify workers: `backend/app/workers/tasks/ml.py:110-132` `run_all_tenant_predictions`→`run_all_predictions` (no Tenant loop — single org); same de-fan-out for `backend/app/tasks/signal_health_rollup.py`, `attribution_variance_rollup.py`, `audience_auto_sync.py`, `apply_actions_queue.py`; `backend/app/workers/celery_app.py` beat entry name `run_all_tenant_predictions`→`run_all_predictions`; sweep remaining `tenant_id` in `workers/tasks/*` (audit, cdp, cms, competitors, creative, forecast, monitoring, rules, scores, sync, whatsapp, helpers) and legacy `workers/tasks.py`
- Modify keys/channels: `backend/app/main.py:820` `events:tenant:{id}`→`events:org` (keep `events:global` for unauthenticated public stream); `backend/app/workers/tasks/helpers.py:78` same; `backend/app/core/websocket.py` — `_publish_to_redis(f"tenant:{tenant_id}",…)` (313)→`"org"` channel, drop `_tenant_connections` map (119) or key it by user only; `endpoints/cdp.py` cache keys `profile:{tenant_id}:{pid}`→`profile:{pid}`, `lookup:{tenant_id}:…`→`lookup:…` (224–295), limiter keys `segment:{tenant_id}`→`segment:global` (3422), `funnel:{tenant_id}` (4423); `endpoints/audit_services.py:116` `{tenant_id}:{user_id}`→`{user_id}`; `endpoints/assets.py:159` `{tenant_id_safe}/{unique_name}`→`{unique_name}` (keep traversal guard); `services/storage.py` doc comment; CSV filenames `cdp_profiles_{tenant_id}.csv`→`cdp_profiles.csv` (cdp.py:1134/1263/2189); OAuth state `{tenant_id}:{state}`→`{state}` (integrations.py:213); campaign_builder redirect path (215)
- Modify metrics: `backend/app/core/metrics.py` — drop `tenant_id` from every `labelnames` (32–182); delete `active_tenants` gauge (174), `tenant_api_requests_total` (179), `request_by_tenant_instrumentation()` (400) + its wiring in `main.py` (standard route/method/status labels remain via Instrumentator)
- Test: new `backend/tests/unit/test_cache_denamespaced.py` — cache round-trip proof (spec §10)

- [ ] **Step 1: Failing cache round-trip test:**

```python
@pytest.mark.asyncio
async def test_cdp_profile_cache_roundtrip_no_tenant_segment(fake_redis) -> None:
    """§10: reads hit writes; key carries no tenant segment."""
    from app.api.v1.endpoints.cdp import _profile_cache_key  # adjust to actual builder name
    key = _profile_cache_key(profile_id=42)
    assert "tenant" not in key and key == "profile:42"
    await fake_redis.set(key, "x")
    assert await fake_redis.get(key) == b"x"
```

- [ ] **Step 2:** PII single-key change + runbook; port `tests/unit` PII tests (drop per-tenant DEK cases from AUTH-05 like `test_cross_tenant_pii_decrypt` — superseded).
- [ ] **Step 3:** Workers de-fan-out + beat rename; keys/channels sweep; metrics de-labeling.
- [ ] **Step 4:** Acceptance greps: `git grep -nE "\{tenant" -- backend/app` empty; `git grep -n "tenant_id" -- backend/app` empty.
- [ ] **Step 5:** Full unit suite green (integration deferred to C6 — schema).
- [ ] **Step 6:** Commit — `refactor(core,workers): single PII key, de-namespaced keys/channels/metrics, single-org tasks [STRAT-SC-001]`

### Task C5: Config + env cleanup

**Files:**
- Modify: `backend/app/core/config.py` — remove any remaining tenant-shaped settings (grep `tenant`); keep everything else per spec §7
- Modify: `backend/.env.example`, root `.env.example` — reflect final var set (no STRIPE_*, no LICENSE_*, no tenant vars); add `ENABLE_PUBLIC_SIGNUP` if missing
- Modify: `backend/app/features/` + `endpoints/feature_flags.py` — flags read org-level (Organization.feature_flags) instead of per-tenant

- [ ] **Step 1:** Sweep + boot check.
- [ ] **Step 2:** Commit — `refactor(config): purge tenant/billing env surface [STRAT-SC-001]`

### Task C6: Fresh Alembic chain + seeds

**Files:**
- Delete: all 61 files in `backend/migrations/versions/` (keep `__init__.py`, `env.py`, `script.py.mako`)
- Create: `backend/migrations/versions/<ts>_001_initial_schema.py` — autogenerated from final models; hand-add at top of `upgrade()`: `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` (must precede `copilot_doc_chunks`); every rescoped constraint line carries `# was tenant-scoped; now global`; working `downgrade()`
- Modify: `scripts/seed-data.sql` — replace demo-tenant insert with `organization` (id=1) + owner user; `scripts/init-db.sql` unchanged (extensions); `backend/scripts/seed_owner.py` seeds owner against Organization
- Modify: `backend/migrations/env.py` if it imports deleted modules

- [ ] **Step 1:** `cd backend && alembic revision --autogenerate -m "initial schema single-client"` against a fresh dockerized pgvector DB (`docker compose up -d db redis`).
- [ ] **Step 2:** Review the migration: pgvector first; FK indexes present on all FKs (audit per spec §4.8); constraint comments added.
- [ ] **Step 3:** `alembic upgrade head && alembic downgrade base && alembic upgrade head` — clean both ways.
- [ ] **Step 4:** Run `python scripts/seed_owner.py`; then FULL suite: `python -m pytest tests -x -q` — this is the phase-C green gate. Fix stragglers (conftest fixtures that made tenants now make/get the Organization singleton + owner user).
- [ ] **Step 5:** Commit — `feat(db): fresh alembic chain 001; organization + owner seeds [STRAT-SC-001]`

---

## Phase D — Frontend tenancy removal

### Task D1: Delete the `/app/:tenantId/*` twin shell

**Files:**
- Delete: `frontend/src/views/TenantLayout.tsx`, `frontend/src/views/tenant/` (49 files), `frontend/src/components/tenant/TenantSwitcher.tsx`
- Modify: `frontend/src/App.tsx` — remove twin routes (lines ~1561–1885); add legacy redirect `/app/:tenantId/*`→`/dashboard/*` (tenant segment discarded, spec §5.1):

```tsx
{/* legacy multi-tenant bookmarks: /app/7/campaigns -> /dashboard/campaigns */}
<Route path="/app/:tenantId/*" element={<LegacyTenantRedirect />} />
```

```tsx
// components/routing/LegacyTenantRedirect.tsx
import { Navigate, useLocation, useParams } from 'react-router-dom';

export default function LegacyTenantRedirect() {
  const { tenantId } = useParams();
  const { pathname, search } = useLocation();
  const rest = pathname.replace(`/app/${tenantId}`, '') || '/overview';
  return <Navigate to={`/dashboard${rest}${search}`} replace />;
}
```

  Also confirm `/overview`→`/dashboard/overview` and `/dashboard/superadmin/*`→`/console/*` redirects exist (App.tsx:2089-2124 — keep).
- Modify: any importer of deleted twin views (`git grep -ln "views/tenant/\|TenantLayout\|TenantSwitcher" frontend/src`)
- Test: `LegacyTenantRedirect.test.tsx` (renders redirect target `/dashboard/campaigns` for `/app/7/campaigns`)

- [ ] **Step 1:** Failing redirect test → implement → pass.
- [ ] **Step 2:** Delete twin; fix importers; `tsc --noEmit` + vitest green.
- [ ] **Step 3:** Commit — `refactor(frontend): remove /app/:tenantId twin shell; legacy redirect [STRAT-SC-001]`

### Task D2: `tenantStore` → `appStore`; remove X-Tenant-ID

**Files:**
- Rename: `frontend/src/stores/tenantStore.ts`→`appStore.ts` — `useTenantStore`→`useAppStore`; delete `tenantId`/`tenant` state, `setTenantId`/`setTenant`, `localStorage['tenant_id']` mirror (lines 122–137); persist key `stratum-tenant-store`→`stratum-app-store`; persist only `dateRange`/`selectedPlatforms`/`selectedBrand`/`isOwnerMode` (add `selectedBrand` for Brand filter per spec §5.4; never persist bypass flags); keep computed `isOwner/isAdmin/hasRole/hasFeature`
- Modify: `frontend/src/api/client.ts` — delete `X-Tenant-ID` injection (line 75) + `getTenantId`/`setTenantId`/`currentTenantId` (46–61); keep 401 refresh mutex byte-for-byte
- Modify: `frontend/src/contexts/AuthContext.tsx` — drop `tenant_id` decode/sync (113–117, 181–197), `User.tenant_id` field; keep `user_type`/`client_id`/`cms_role` (Brand/portal — NOT tenancy)
- Modify: all `useTenantStore` importers (`git grep -ln useTenantStore frontend/src`)
- Test: update `frontend/src/api/client.test.ts` (remove header assertions at 183/190, add negative assertion `expect(cfg.headers['X-Tenant-ID']).toBeUndefined()`); store tests renamed

- [ ] **Step 1:** Failing client test (no X-Tenant-ID) → implement → pass.
- [ ] **Step 2:** Store rename sweep + AuthContext; `tsc` + vitest green.
- [ ] **Step 3:** Acceptance: `git grep -in "x-tenant-id\|tenant_id" -- frontend/src` empty.
- [ ] **Step 4:** Commit — `refactor(frontend): appStore replaces tenantStore; drop X-Tenant-ID [STRAT-SC-001]`

### Task D3: Console cleanup + CrossAccountAnomalies

**Files:**
- Delete: `frontend/src/views/superadmin/TenantsList.tsx`, `TenantProfile.tsx` (Billing.tsx already gone in A4), `frontend/src/views/Tenants.tsx`, `frontend/src/components/client/ClientContextSwitcher.tsx` **only if** it switches tenants — if it switches Brands (clients), KEEP (Brand model is preserved)
- Rename: `frontend/src/views/console/CrossTenantAnomalies.tsx`→`CrossAccountAnomalies.tsx` (same detection logic; copy strings from "tenant" to "account/brand"); update route `/console/anomalies` element + `consoleNav.ts` label
- Modify: `frontend/src/App.tsx` — remove `/console/tenants`, `/console/tenants/:tenantId`, `/dashboard/tenants` routes; `frontend/src/api/hooks/useConsole.ts` (ex-useSuperAdmin) — drop tenant list/profile queries; `frontend/src/components/primitives/nav/consoleNav.ts` — drop Tenants/Billing entries
- Modify: `vercel.json` — remove `/tenants`, `/tenants/:path*`, `/superadmin`, `/superadmin/:path*` rewrites (17–20); regenerate remaining set against final routes
- Modify: i18n `frontend/src/i18n/locales/{en,ar}/translation.json` — remove tenant/billing/pricing keys (4 keys en)
- Delete: `frontend/e2e/tenant-flows.spec.ts`
- Test: `tsc` + vitest + `npx playwright test --list` (specs enumerate without the tenant spec)

- [ ] **Step 1:** Verify `ClientContextSwitcher` semantics (read the file) — Brand switcher stays.
- [ ] **Step 2:** Apply deletions/renames/route edits; green checks.
- [ ] **Step 3:** Acceptance: `git grep -iln "tenant" -- frontend/src` returns empty (or only Brand-domain false positives — resolve each by renaming strings).
- [ ] **Step 4:** Commit — `refactor(frontend): drop tenant console views; CrossAccountAnomalies [STRAT-SC-001]`

---

## Phase E — CI residue gate, docs, final validation

### Task E1: CI residue gate + workflow updates

**Files:**
- Modify: `.github/workflows/ci.yml` — new first job:

```yaml
  residue-gate:
    name: Removed-scope residue gate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: No tenant/stripe residue in source
        run: |
          set -e
          EXCL=':!*.md :!*.html :!*.txt :!*.xlsx :!*.zip :!*.csv :!datasets :!audit :!superads-dashboard :!docs :!backend/docs :!chat.md'
          if git grep -I -iE 'tenant_id|X-Tenant-ID|stripe' -- . $EXCL; then
            echo '::error::removed-scope residue found'; exit 1; fi
          if git grep -I -nE '\{tenant' -- . $EXCL; then
            echo '::error::tenant-namespaced key builder found'; exit 1; fi
```

  and add `residue-gate` to the release-gate job's `needs`. Fix ci.yml:174 comment mentioning TenantMiddleware.
- Modify: `.github/workflows/docker.yml` — nothing tenant-shaped expected; verify compose-test still healthy

- [ ] **Step 1:** Run the gate command locally — must exit clean before committing.
- [ ] **Step 2:** Commit — `ci: residue gate for tenant/stripe removal [STRAT-SC-001]`

### Task E2: Docs + CLAUDE.md alignment

**Files:**
- Modify: `CLAUDE.md` — remove feature rows 11 (Payments) and 12 (Multi-tenancy); `middleware/` description drops "Tenant"; Domain Terminology drops "Tenant" row; Trust Engine comment "per tenant"→"org-configurable (Organization settings)"; superadmin→console/owner in feature 14; re-apply the stashed docs trim if desired (`git stash list` → the `wip: CLAUDE.md docs trim` stash)
- Modify: `README.md`, `SECURITY.md`, `backend/docs/**` shipped for RAG — sweep tenant/billing mentions that describe CURRENT behavior (historical docs/changelogs stay; they're .md and gate-excluded anyway)
- Create: `docs/single-client-conversion.md` — one-page record: removal ledger applied, §4.9 behavior changes, key de-namespacing map, fresh-chain note

- [ ] **Step 1:** Edits + commit — `docs: align CLAUDE.md and docs with single-client architecture [STRAT-SC-001]`

### Task E3: Final validation (spec §10 subset applicable to conversion)

- [ ] `cd backend && make check` green (lint + mypy + unit tests)
- [ ] `cd backend && python -m pytest tests/integration -q` green
- [ ] `cd frontend && npm run build` green (`tsc --noEmit` + vite)
- [ ] `docker compose up -d` → all services healthy; `/health/ready` 200 after DB+Redis
- [ ] Residue gate grep clean (E1 command locally)
- [ ] Global-uniqueness tests all present + passing; each converted constraint commented
- [ ] Cache round-trip test passing; `git grep -nE '\{tenant' backend/app` empty
- [ ] Trust gate: `test_trust_gate_org_config.py` proves thresholds read from Organization settings; autopilot suite green (never execute <70)
- [ ] Auth: MFA login flow integration tests green; blacklist fail-open test green; no PII/tenant claims in JWT
- [ ] `alembic upgrade head` + `downgrade base` clean on fresh DB
- [ ] Playwright: `npx playwright test --project=chromium` (auth/dashboard/onboarding at minimum)
- [ ] Commit any fixups; leave branch local (user directive: no push/PR) and summarize against the §0.1 ledger

---

## Self-review notes (already applied)

- Spec coverage: ledger rows 1–20 map to tasks — Tenant/membership→C1, TenantMixin→C1, middleware/header/tenancy→C2, per-tenant PII keys→C4, from_tenant_settings→C3, tenants/tenant_dashboard endpoints→C2, subscription/tier/payments/stripe_webhook→A2, stripe SDKs→A2/A4, TierGate/402/UpgradePrompt/TierContext→A1/A4, editions→A3, provisioning+licensing+limits→A3, tenant twin shell→D1, console tenant/billing views→A4/D3, CrossTenantAnomalies→D3, pricing/plans/checkout pages→A4, Stripe env→A2, billing beats→A2, tenant metrics→C4, superadmin rename→B1/B2. §4.9→C1+C6, §4.8 keys→C4, §6.4 gate→E1.
- Known risk: C3 is the largest task; if it exceeds a session, split by directory at the checkpoints already marked (Steps 2/3/4 are commit-safe boundaries within the C1–C6 PR).
- Out of scope (spec-permitted): §12 live-DB conversion; building the rotation script (runbook documents it); regenerating all ~45 vercel rewrites beyond removals.

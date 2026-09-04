# Stratum Single-Client Project Guide

This repository is the single-client conversion of the Stratum/ADs Growth System. It retains the Trust-Gated Autopilot and analytics platform, but tenant isolation, subscription tiers, licensing, and payment processing were deliberately removed.

Do not copy multi-tenant or Paddle billing behavior from **Stratum-AI-Final-Meta** or **Stratum-AI-Final-Updates-Dec-2025** into this repository. Historical Stripe references remain in audits and older feature documents; live source is protected by the removed-scope CI gate.

## Safety model

Automation may execute only when signal health is at least 70 and every authorization, policy, limit, idempotency, and audit check passes. Scores from 40–69 hold; scores below 40 block. Missing or stale data must fail closed.

Threshold logic has multiple consumers. Trace the active implementation and tests before changing it; do not add another hardcoded copy.

## Sources of truth

Prefer registered code and tests, then **.github/workflows/ci.yml**, Makefiles, Docker/Compose, current environment examples, and **docs/single-client-conversion.md**. Dated audits and pre-conversion feature documents are historical evidence.

## Repository map

- **backend/app/** — FastAPI API, trust/autopilot, analytics, auth, services, and Celery workers
- **backend/migrations/** — fresh single-client Alembic chain
- **backend/tests/** — unit and integration tests
- **frontend/src/** — React/Vite application
- **docs/single-client-conversion.md** — removal ledger and conversion boundaries

## Commands

~~~bash
make dev
make test
make test-all
make test-cov
make lint
make format
make migrate
make migration msg="description"
make check
~~~

From **frontend/** run npm CI, lint, TypeScript checks, coverage tests, build, and Playwright using the scripts in its package manifest.

## Engineering rules

- Preserve the single-client model. Do not reintroduce tenant IDs, tenant middleware, subscription gates, Stripe, Paddle, licensing, or plan limits.
- Never bypass the trust gate or report a successful data sync when no metrics were written.
- Keep authentication, role checks, enforcement limits, and audit logging around mutations.
- Use Pydantic API models, established async SQLAlchemy patterns, timezone-aware UTC, and encrypted credential storage.
- Append Alembic migrations; never rewrite applied history.
- Keep secrets and PII out of source, JWT claims, browser code, and logs.
- Treat CI’s final aggregator as the release gate, including checks that collect earlier nonfatal step results.

Keep frontend behavior bilingual, RTL-safe, accessible, and aligned with backend schemas.

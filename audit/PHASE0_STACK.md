# PHASE 0 — ENVIRONMENT & STACK DISCOVERY
Audit date: 2026-07-18 · Auditor: post-conversion systems audit (v2.0 protocol)
Repo root: `C:\Users\Vip\Desktop\Stratum-AI-Final-Single Client\Stratum-AI-Final-Single Client` (note: nested one level below the working directory; outer folder is not a git repo)

## 1. Repository & Conversion Location

| Item | Evidence |
|---|---|
| Git branch | `main`, tracking `origin/main`, clean except untracked `STRATUM_AI_REBUILD_PROMPT.md` (`git status -sb`) |
| Conversion ticket | **STRAT-SC-001** ("single-client conversion") |
| Conversion branch | `feature/STRAT-SC-001-single-client-conversion`, tip `04ba89e5` — **fully merged into main** (`git merge-base --is-ancestor 04ba89e5 main` → true; `git log main..feature/…` → empty) |
| Conversion commit range (primary suspect list) | `4a68bf4a` (decouple tier gating) → `04ba89e5` (terminology sweep). Key commits: `0fbe2870` Organization singleton, drop Tenant/tenant_id; `198b262d` AuthContextMiddleware replaces TenantMiddleware; `0eb71c73` remove tenant_id threading across endpoints/services; `d409a7e0` single PII key, de-namespaced keys/channels/metrics; `43eebd09` purge tenant/billing env surface; `3c21edb8`/`274b34da`/`691eaf0b`/`c135fa20` frontend de-tenanting; `5e9ac004`/`4a68bf4a` billing/licensing removal; `60839ea2` superadmin→owner rename |
| Post-merge residue fixes on main | `dcf4615e` (last three model renames), `64976e76` (frontend token sweep + tenant residue rename), `9ded8315` (CI green, residue-gate regex) |
| Post-conversion feature work on main | OAuth onboarding wizard (STRAT-OW-001), credential-resolution fixes (`aa8a32da`, `3a21210d`), client installer/deploy kit (`8372ccc2`, `953aa145`), Opal Hotel rebrand (4 commits, frontend theme only) |
| CI enforcement of conversion | `.github/workflows/ci.yml:27` — dedicated **"Removed-scope residue gate"** job greps source for tenant/stripe residue and fails the build; final gate at line 547 requires it |

## 2. Languages & Frameworks

### Backend (`backend/`)
- **Python 3.11** (`backend/Dockerfile: FROM python:3.11-slim-bookworm`)
- **FastAPI 0.139.2** + **uvicorn 0.51.0** (`backend/requirements.txt`)
- **SQLAlchemy 2.0.51 (asyncio)** + **asyncpg 0.31.0** (async ORM) + psycopg2-binary 2.9.12 (sync/migrations)
- **Alembic 1.18.5** — migrations in `backend/migrations/versions/` (**4 entries incl. `__pycache__`; 3 real migrations**):
  - `20260714_152542_12a656044fcc_initial_schema_single_client.py` ← squashed single-client initial schema
  - `20260715_101500_b7e3f4a9c2d1_rename_tenant_prefixed_tables.py` ← tenant-prefixed table renames
  - `20260717_020000_c8d2e5f7a1b3_add_platform_app_credential.py`
- **Celery 5.6.3** + **celery-redbeat 2.4.1** (Redis-backed beat scheduler). Celery app: `backend/app/workers/celery_app.py`; tasks in `backend/app/workers/tasks*/` and `backend/app/tasks/`
- **Pydantic 2.13.4** + pydantic-settings (config)
- App entry point: `backend/app/main.py` — app factory at line 273 (`FastAPI(...)`), routers mounted at line 506 (`app.include_router(api_router, prefix=settings.api_v1_prefix)`)
- Package layout: `app/{api,auth,middleware,core,db,models,schemas,services,workers,tasks,ml,ml_service,analytics,autopilot,features,monitoring,quality,stratum,domain,scripts}`

### Frontend (`frontend/`)
- **React 19.2.7** + **TypeScript** + **Vite**; TanStack Query 5, axios; Node 26-alpine build (`frontend/Dockerfile`)
- Tests: **vitest** (unit) + **Playwright** (e2e, `frontend/e2e/`)
- Realtime client code exists: `frontend/src/hooks/useWebSocket.ts` (+ test) — server counterpart TBD in Phase 8
- Also present: `superads-dashboard/` (separate dashboard app — inventory in Phase 1)

## 3. Infrastructure Subsystems

| Subsystem | Implementation | Evidence |
|---|---|---|
| Database | **PostgreSQL 16 + pgvector** | `docker-compose.yml` service `db: image: pgvector/pgvector:pg16` |
| Queue/broker | **Redis 7** (Celery broker + redbeat) | compose service `redis: image: redis:7-alpine`; celery-redbeat in requirements |
| Cache | Redis (same instance; `redis[asyncio] 8.0.1` client) | requirements.txt |
| File storage | **S3 via boto3** (`backend/app/services/storage.py`) + local `backend/uploads/` | grep boto3/S3 hits: `services/storage.py`, `api/v1/endpoints/assets.py`, `services/reporting/delivery.py` |
| Realtime | WebSocket hook on frontend; backend server-side presence unconfirmed | `frontend/src/hooks/useWebSocket.ts` — **Phase 8 must locate/confirm server endpoint** |
| Email | Resend (per deployment memory); SMTP config TBD Phase 8 | `.env.example` review pending |
| Monitoring | `monitoring/` + `docker-compose.monitoring.yml`; Flower for Celery; prometheus-fastapi-instrumentator (dependabot branch exists) | compose service `flower` |
| Reverse proxy | `nginx/` (compose), `frontend/nginx.conf`, Caddy TLS in `deploy/` client-installer kit | commit `8372ccc2` |

## 4. Configuration & Environments
- `.env` (29 keys, local dev), `.env.example` (70 keys), `.env.production.example`, `.env.production.template`
- Compose stacks: `docker-compose.yml` (dev: db, redis, api, worker, scheduler, frontend, flower), plus `.beta`, `.dev`, `.staging`, `.prod`, `.monitoring` variants
- Railway deployment: `backend/railway.toml`, `railway.worker.toml`, `railway.beat.toml`, `frontend/railway.toml` (prod is live on Railway per project memory)
- `deploy/` — self-hosted client installer kit (registry-pull compose, Caddy TLS)

## 5. CI/CD
- **GitHub Actions** `.github/workflows/ci.yml`: jobs = residue-gate → backend-quality, backend-tests, backend-security, frontend (vitest + build), e2e, security, secrets; final aggregation gate at line 547. `docker.yml` = image build/push (ghcr.io).
- **CircleCI** `.circleci/config.yml` also present — likely stale duplicate; verify in Phase 12.
- Note: GitHub Actions was billing-locked recently (project memory) — CI green status on main unverified.

## 6. How to Boot & Test (as documented)
- Full stack: `docker compose up` from repo root (dev compose)
- Backend only: `make dev` (root Makefile delegates to `backend/Makefile`); tests: `make test` / `make test-all` / `make test-cov` (pytest, `backend/pytest.ini`); migrations: `make migrate` (alembic)
- Frontend: `npm run dev` / `npm test` (vitest) / `npm run test:e2e` (Playwright) in `frontend/`
- Windows host, Docker required for Postgres+pgvector/Redis. Existing scratch DBs were recreated after table renames (project memory: containers renamed `*_old_dec2025`).

## 7. Phase 0 Health Assessment
**HEALTHY — stack fully mapped.** Entry points, subsystems, boot and test procedures are all identified. No unbuildable-project finding at this stage (build/boot verification itself is deferred to Phase 13).

Watch-list seeded for later phases:
1. Backend WebSocket server counterpart for `useWebSocket.ts` (Phase 8)
2. Only 3 alembic migrations — history was squashed; fresh-install semantics + `fix_alembic_version.py` at `backend/` root smells like a past migration-state repair (Phases 4, 12)
3. `superads-dashboard/` unaccounted for (Phase 1)
4. CircleCI config vs GitHub Actions duplication (Phase 12)
5. Billing/licensing was *removed* (not converted) — Stripe residue gated in CI (Phases 2, 9)
6. `backend/celerybeat-schedule` file committed at backend root despite redbeat (Redis) scheduler (Phase 6)

## 8. Findings Count
Phase 0 findings: **0** (no BROKEN/DEGRADED yet; discovery only).

# PHASE 13 — RUNTIME SMOKE VERIFICATION
Audit date: 2026-07-18.

## Scope declared
Boot the app, run migrations against a scratch DB, exercise top critical paths (login+refresh, a read, a write, a background job, a file upload), record exact commands/outputs. Anything not exercisable → UNTESTABLE with the precise required check. Findings: **2 new** (0 CRITICAL, 2 MEDIUM), plus **runtime CONFIRMATION of 5 prior findings** and 1 robustness note.

## Environment (what was available)
- Python 3.12.10 (project targets 3.11), Node 22, Docker 29. Docker daemon was down at phase start, then the user restarted Docker Desktop.
- Postgres (pgvector/pg16) `stratum_db` and Redis 7 `stratum_redis` containers already running (from a prior session), HEALTHY on 5432/6379.
- **Env drift observed**: the running containers' credentials differ from the repo `.env` (DB pwd `BUvW…`; Redis `--requirepass bARE…`), and `localhost`→`::1` (IPv6) with the async clients' 1s timeout — environment setup friction, **not app bugs**. Also: installed `fastapi 0.129.0` vs `0.139.2` pinned in requirements (dependency drift; app runs).
- Result: a **full local boot was achieved** against a freshly-migrated scratch DB (`audit_scratch`) + Redis, and the core critical paths were exercised live. This RAISES the report's confidence ceiling substantially — the auth core, de-tenanting, migration-from-zero, and the 5-1 breakage are now runtime-proven, not static-only.

## RUNTIME CONFIRMATION of prior findings (live evidence)
| Prior finding | Runtime evidence | Verdict |
|---|---|---|
| **FINDING-5-1** (stacked-prefix 404s) | Live HTTP on booted API: `GET /api/v1/audit-services/experiments` → **404**; real `GET /api/v1/audit/audit-services/health` → **200**. Route table: 615 routes; all 4 double-prefixes served (`/audit/audit-services`=38, `/console/analytics/console`=3, `/intelligence/analytics/insights`=3, `/compliance/admin/compliance`=7); every FE-called single-prefix path absent. | **CONFIRMED (runtime)** |
| **FINDING-5-4** (embed public router unmounted) | Route table: `/api/v1/embed/v1/*` = **not present**; `/embed-widgets` present; `memory_debug` absent. | **CONFIRMED (runtime)** |
| **FINDING-6-1** (stranded queues) | Celery app import: `task_default_queue=default`, worker (no -Q) consumes only `default`; 4 beat entries routed to non-default queues (sync-all-campaigns→sync, generate-daily-forecasts→ml, run-all-predictions→ml, audience-auto-sync-sweep→sync); all 4 `task_routes` keys `registered as-is? False`. | **CONFIRMED (runtime)** |
| **FINDING-4-1** (enforcement_settings no singleton guard) | Migrated scratch schema: `SELECT count(*) FROM pg_constraint WHERE conrelid='enforcement_settings' AND contype='c'` → **0** check constraints. | **CONFIRMED (runtime)** |
| **Phase 2/4 de-tenanting** | Migrated schema: `information_schema.columns` with `%tenant%` → **0**; `tables LIKE 'tenant%'` → **none**. Org singleton `ck_organization_ck_organization_singleton` present; `uq_user_email_hash` + all `uq_platform_*` uniques present. | **CONFIRMED (runtime)** |
| **Phase 3 auth core** | Live: login → 200 (JWT payload `{"sub":"4","type":"access","role":"owner","cms_role":null}` — **no tenant claim**); refresh → 200 (new token); unauth `GET /campaigns` → **401**. | **CONFIRMED (runtime)** |
| **Phase 12 fresh-install** | `alembic upgrade head` on empty `audit_scratch` ran all 3 migrations cleanly (12a656044fcc→b7e3f4a9c2d1→c8d2e5f7a1b3); single head. Owner seed succeeded. | **CONFIRMED (runtime)** |

## Critical-path smoke results (booted API on 127.0.0.1:8139, scratch DB)
| Path | Result | Evidence |
|---|---|---|
| Login | ✅ 200 | access+refresh issued, role=owner, no tenant claim |
| Token refresh | ✅ 200 | new access_token issued (rotation) |
| Read (`/users/me`) | ✅ 200 | user payload returned |
| Read (`/assets` list) | ✅ 200 | `{items:[],total:0}` (correct empty on fresh DB) |
| Write (`PATCH /users/me`) | ✅ 200 | persisted — `updated_at` advanced |
| Auth guard (unauth `/campaigns`) | ✅ 401 | protected route rejects anonymous |
| FINDING-5-1 live | ✅ reproduced | FE path 404 / real path 200 |
| File upload (`POST /assets` multipart) | ⚠️ UNTESTABLE | HTTP 000 (connection reset on multipart); server survived (login 200 after). Needs a cleaner multipart client to confirm — see UNTESTABLE register. |
| Background job execution | ⚠️ not run | Would need worker+beat+broker up; FINDING-6-1 confirmed by Celery import instead. |

## NEW FINDINGS (discovered at runtime)

```
FINDING-13-1
Feature:        App startup / owner auto-seed (FEAT-005, deploy)
Status:         BROKEN
Severity:       MEDIUM
Confidence:     HIGH (observed live crash)
What is broken: The API fails to boot entirely when SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD are
                unset — even though the startup owner-seed is written as BEST-EFFORT. The lifespan
                (main.py:234-241) does `try: from scripts.seed_owner import create_owner;
                await create_owner() except Exception: logger.warning(...)`. But importing
                scripts.seed_owner executes its module-level guard (seed_owner.py:45-52) which calls
                `sys.exit(1)` when those env vars are absent. `sys.exit` raises SystemExit, which is
                NOT a subclass of Exception, so it ESCAPES the `except Exception` → "Application
                startup failed. Exiting."
Root cause:     A script with a top-level `sys.exit(1)` is imported inside the app lifespan; the
                best-effort try/except cannot catch SystemExit. (seed_owner.py replaced the old
                per-tenant seed_superadmin.py during the conversion — this is post-conversion code.)
Blast radius:   Any boot without SUPERADMIN_EMAIL/PASSWORD dies at startup with a confusing
                SystemExit traceback instead of the intended "owner_seed_failed" warning + continue.
                Current prod deploys set these vars (SEED_SUPERADMIN flow / installer prompts), so
                it's not biting them — but the graceful-degradation the code intends is silently
                defeated, and a partial/misconfigured deploy gets a hard, opaque boot failure.
Evidence:       Live: booted uvicorn without the vars → log shows import of scripts.seed_owner →
                SystemExit: 1 → "Application startup failed. Exiting." Re-boot WITH the vars → clean
                start + login 200.
Fix:            Guard the import (check the env / a SEED flag BEFORE importing), OR move create_owner
                into a function with no module-level sys.exit, OR catch BaseException around the
                seed. Make best-effort actually best-effort.
Confirm via:    Start the API with SUPERADMIN_EMAIL/PASSWORD unset → currently crashes at startup.
```

```
FINDING-13-2
Feature:        Health endpoints / SPA serving (FEAT-085, FEAT-091, deploy healthcheck)
Status:         DEGRADED
Severity:       MEDIUM
Confidence:     HIGH (observed live)
What is broken: When the API also serves the built SPA (frontend/dist present), the catch-all route
                `/{full_path:path}` (main.py:548) shadows the health endpoints: GET /health,
                /health/ready, /health/live all return 404. The catch-all is registered BEFORE the
                health routes (route table idx 708 vs 709/710/711), and its exclusion branch RAISES
                `HTTPException(404)` for health/api/docs/uploads paths (main.py:551) instead of
                letting them fall through to the real handlers. Starlette matches in registration
                order, so the real /health (idx 709) is never reached.
Root cause:     Ordering + raise-instead-of-passthrough: the SPA catch-all is mounted before the
                health endpoints and 404s the excluded prefixes rather than deferring to later routes.
Blast radius:   The Docker/compose healthcheck is `curl -f http://localhost:8000/health`
                (docker-compose.yml:172, deploy/docker-compose.client.yml:211). In any single-
                container deploy that serves SPA+API from the API image, /health 404s → healthcheck
                fails → container marked unhealthy → restart loop (would be HIGH/CRITICAL there).
                LATENT today because all current topologies (dev compose, client installer, Railway)
                run frontend as a SEPARATE service, so the API container has no frontend/dist and the
                catch-all isn't mounted → /health works. But the code explicitly supports SPA-from-
                API (the mount exists), so this is a live trap for the obvious "simple single-
                container" deployment.
Evidence:       Live (frontend/dist present locally): GET /health → 404 {"detail":"Not Found"};
                GET /ready → 200. Route table: idx 708 /{full_path:path} precedes idx 709 /health.
                main.py:551 `raise HTTPException(404)` in the exclusion branch.
Fix:            Register the SPA catch-all LAST (after all real routes incl. /health), or in the
                exclusion branch fall through instead of raising (e.g. mount SPA as a sub-app so real
                routes win), or define health endpoints before the catch-all mount.
Confirm via:    Run the API with frontend/dist present → GET /health → 404 (should be 200).
```

## Robustness note (observed, minor)
- **N13-a**: `ws_manager.start()` (websocket.py:138-148) catches only `ConnectionError/TimeoutError/OSError` around the Redis ping. A Redis `AuthenticationError` (wrong/missing password) is a `RedisError`, not one of those, so it ESCAPES and crashes startup (observed live when Redis auth was missing). The "operate without Redis" degradation is thus not fully robust to an auth misconfiguration. Low severity (misconfig-only), same family as 13-1 (narrow except clauses defeating intended graceful degradation).

## UNTESTABLE register (from this phase)
| Item | Why inconclusive | Exact runtime check required |
|---|---|---|
| File upload (`POST /api/v1/assets`) | HTTP 000 (connection reset) on multipart; server survived, so not a crash — ambiguous | Re-run with a robust multipart client (e.g. Python `requests` with a real PNG) against a booted API + writable `asset_upload_dir`; assert 200 + row in `digital_assets` + file at `/uploads/assets/<key>`. |
| Background job EXECUTION (stranded-queue live demo) | Worker+beat+broker not started | Start `celery worker` (no -Q) + `celery beat`; enqueue the beat `sync-all-campaigns` (routed to queue `sync`); observe the `sync` queue depth grows in Redis while the worker (bound to `default`) never consumes it — the live proof of FINDING-6-1. |
| Full-stack integration test suite | Container cred/env drift vs repo `.env`; `pytest tests/integration` needs the app's configured DB/redis creds | With matching creds, run `pytest tests/integration -m integration` (conftest does DROP SCHEMA + `alembic upgrade head`); confirm green. |

## Phase 13 summary
Runtime verification was **largely successful** and is the highest-value phase: the app boots, migrations run from zero cleanly, the schema is genuinely de-tenanted (0 tenant columns/tables, verified in-DB), and the core critical paths — login, refresh, authed read, authed write, auth-guard — all pass live. Crucially, **FINDING-5-1 was reproduced over live HTTP** (FE path 404 / real path 200) and FINDINGS 4-1, 5-4, 6-1 were confirmed against the running system. The runtime pass also **discovered two new findings** static analysis had missed: a best-effort owner-seed that hard-crashes startup when its env vars are unset (13-1, SystemExit escaping the guard), and health endpoints shadowed by the SPA catch-all when the API serves the frontend (13-2, latent healthcheck-killer). File upload and the live background-job demo remain UNTESTABLE with precise checks documented. Net effect: the report's confidence ceiling rises from "static-analysis" to "runtime-verified" for auth, migrations, de-tenanting, and the headline routing breakage.

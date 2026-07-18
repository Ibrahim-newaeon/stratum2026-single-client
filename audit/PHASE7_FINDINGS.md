# PHASE 7 — FILES, STORAGE & CACHING
Audit date: 2026-07-18.

## Scope declared
Storage: upload/read path agreement for former tenant-scoped prefixes; legacy-file reachability; signed URLs; per-tenant quotas; media pipelines. Caching: cache-key construction with tenant segments; producer/consumer symmetry; invalidation; stale pre-conversion entries. Healthy = write path == read path, keys carry no orphaned tenant segment, invalidation matches construction. Findings: **0** (all OPERATIONAL). 2 low-risk observations recorded.

## STORAGE — OPERATIONAL (evidence-backed)
- **Object keys are flat, no tenant segment.** `assets.py:156` `object_key = unique_name`; passed to `get_object_storage().save(object_key, …)` (:158). No `f"{tenant}/…"` prefix anywhere (grep for tenant in storage.py/assets.py/delivery.py key builders = 0). Both backends key on the flat string: LocalObjectStorage → `/uploads/assets/{key}` (storage.py:82), S3ObjectStorage → `Bucket={bucket}, Key={key}` (storage.py:115). Write path == read path.
- **Read path cannot drift from write path by construction.** `save()` returns the retrieval URL, which is **persisted in the DB at upload time and served as-is** — the read path never *reconstructs* a key, so there is no producer/consumer path-asymmetry surface (the classic "write to /uploads/<tenant>/x, read from /uploads/x" bug is structurally impossible here).
- **Legacy-file reachability = N/A (greenfield).** Per Phase 4, the deployment starts from an empty schema with no pre-conversion data; there are no files stored at old tenant-scoped paths to become 404s.
- **Path-traversal hardened** (unrelated to conversion but worth noting healthy): `_reject_traversal` (storage.py:50-56) + resolved-path containment check (:74-77).
- **Signed URLs** (storage.py:125-128): S3 backend returns a stable public URL when `asset_s3_public_base_url` is set, else a presigned GET with `PRESIGN_EXPIRY_SECONDS` TTL. No tenant in URL construction.
- **Reporting artifacts** (services/reporting/delivery.py:565): `s3_key = f"{prefix}/{timestamp}/{filename}"` — prefix + timestamp + filename, no tenant segment; presigned GET generated from the same key (:583-585). Symmetric.
- **Per-tenant storage quota = absent.** grep for quota/max_storage/storage_limit → only API-rate-limit comments (`signal_health_rollup.py:166`, `stratum/adapters/*`); no per-tenant storage quota logic left to orphan or misapply.

## CACHING — OPERATIONAL (evidence-backed)
- **Zero tenant residue in cache keys** (grep tenant in core/ = 0; confirms conversion commit d409a7e0 "de-namespaced keys/channels/metrics"). Every key observed is tenant-free and built identically on read and write:
  - CAPI dedupe: `f"{key_prefix}{event_key}"` (distributed_dedupe.py:171/310/341); invalidation pattern `f"{key_prefix}*"` (:374) matches the same prefix — producer/consumer symmetric.
  - EMQ measurement: `f"{platform}_{period_hours}"` (emq_measurement_service.py:467) — same key for set (:506) and get (:470).
  - Token blacklist: `f"{TOKEN_BLACKLIST_PREFIX}{jti}"` (security.py:322/344) — write and read identical.
  - OAuth state: `setex(key, OAUTH_STATE_EXPIRY, …)` (oauth/base.py:166) — CSRF state, symmetric.
  - Login lockout: `setex(lockout_key, …)` (security.py:395) — symmetric.
- **Invalidation matches construction** — no case found where a producer writes key X but the invalidator clears key Y (the dedupe wildcard and the per-key deletes both use the same prefix).
- **No Redis pub/sub tenant channels**: `core/websocket.py` channel subscriptions are free-form client-driven names with no tenant namespace in the manager (channel *content* audited in Phase 8).

## Observations (low-risk, NOT findings)
- **OBS-7-a — stale pre-conversion cache entries (low risk).** Prod Redis was converted in place (project memory). Any old tenant-namespaced keys (e.g. former `tenant:*`) are now **orphaned**: the new code builds tenant-free keys, so it never reads the old ones, and all keys observed carry TTLs (setex/expire) → they expire unused. No poisoning path (new reads can't accidentally hit old keys — the strings differ). Belt-and-suspenders: a one-time `FLUSHDB` on the cache DB at the conversion deploy removes them immediately; optional, not required.
- **OBS-7-b — EMQ per-process cache (pre-existing, not conversion).** `emq_measurement_service._cache` is an in-process dict, not distributed Redis, so each API worker caches independently (lower hit rate, brief cross-worker inconsistency within the TTL). Pre-existing design, tenant-unrelated; flag only for future consolidation.

## Phase 7 summary
Storage and caching are **fully de-tenanted and internally symmetric**. Flat object keys stored-then-served (no reconstruction), tenant-free cache keys with matching invalidation, no per-tenant quota residue, and greenfield deployment eliminating legacy-file/stale-entry hazards. This is the cleanest phase so far — the de-namespacing work (d409a7e0) was thorough. No findings; two low-risk observations for hygiene.

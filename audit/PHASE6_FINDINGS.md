# PHASE 6 — BACKGROUND JOBS, QUEUES & SCHEDULED TASKS
Audit date: 2026-07-18.

## Scope declared
Task payloads/consumers dereferencing an absent `tenant_id`; "for each tenant" jobs (run once/zero/crash?); producer↔consumer queue+name agreement; `task_routes` mismatch; unregistered CRM module with live `.delay()`; orphaned tasks; the two legacy standalone Celery apps; idempotency/DLQ/retry. Healthy = every enqueue reaches a registered consumer on a consumed queue; no task needs tenant context. Findings: **4** (0 CRITICAL, 1 HIGH, 2 MEDIUM, 1 LOW).

## What is HEALTHY (evidence-backed)
- **Task signatures fully de-tenanted** (agent-verified): NO `@task`/`@shared_task` still declares a `tenant_id`/`org_id` param; NO producer passes one; NO consumer dereferences `payload["tenant_id"]`. All `tenant`/`org` hits in the worker layer are comments or UI/schema field names. This failure class ("consumer dereferences a now-absent field") is **absent**.
- **No per-tenant loop remnants**: every fan-out (`sync_all_campaigns`, `evaluate_all_rules`, `compute_all_cdp_*`, `run_all_predictions`, rollups) iterates a domain-entity set (Campaign/Rule/CDPSegment/PlatformAudience rows), runs once correctly in single-org, and does nothing on an empty due-set (correct). No task iterates a removed tenant collection → none silently no-op via empty-set or crash on a missing tenant table.
- **On-demand enqueues work**: `.delay()` from endpoints (sync now, publish, send newsletter, run predictions, whatsapp) target registered tasks and land on the `default` queue, which the worker consumes.
- **DLQ path intact**: task-failure hook `send_task("dead_letter_sink", queue="dead_letter")` (celery_app.py:269) → registered sink (:313).
- **Idempotency keys carry no tenant residue**: rollups upsert by `(date, platform)`; capi `ix_dedupe_key` unique on `dedupe_key` alone — no tenant segment lost.
- **Registration gaps the team already fixed** are real fixes (verified in `include`): apply_actions_queue, signal_health_rollup, attribution_variance_rollup, audience_auto_sync, newsletter_tasks are all now registered (celery_app.py:19-44), with code comments documenting the prior silent-no-op bugs.

## FINDINGS

```
FINDING-6-1
Feature:        FEAT-100 (campaign sync), FEAT-101 (forecasts), FEAT-106 (predictions),
                FEAT-111 (audience auto-sync) — and the whole sync/ml/intel/rules queue design
Status:         BROKEN
Severity:       HIGH
Confidence:     HIGH (CONFIRMED)
What is broken: The beat scheduler dispatches several core recurring tasks to Celery queues
                "sync"/"ml"/"intel"/"rules" via explicit `"options": {"queue": …}`, but the ONLY
                worker deployment is launched with NO `-Q` flag, so it consumes just the default
                queue (task_default_queue="default", celery_app.py:70). Tasks published to the
                other queues have NO consumer — they accumulate in the broker and NEVER execute.
                Stranded recurring jobs (queue ≠ default):
                  - sync-all-campaigns  (hourly)  → queue "sync"  (celery_app.py:101)
                  - generate-daily-forecasts (06:00) → queue "ml" (:107)
                  - run-all-predictions (*/30 min) → queue "ml"  (:144)
                  - audience-auto-sync-sweep (*/15) → queue "sync" (:187)
                  - [gated] sync-all-ad-accounts→sync (:206), evaluate-active-rules→rules (:241),
                    refresh-competitor-data→intel (:252)
                Tasks on the default queue DO run (audit logs, heartbeat, pipeline health, fatigue,
                daily scores, whatsapp, apply-actions, signal-health rollup, attribution rollup).
Root cause:     (1) Worker launched without queue binding: `celery -A app.workers.celery_app worker
                --concurrency=…` in docker-compose.yml:271, deploy/docker-compose.client.yml:312,
                railway.worker.toml:27 — none pass `-Q sync,ml,intel,rules`. (2) Compounding it, the
                `task_routes` map (celery_app.py:80-85) is dead: its keys
                ("app.workers.tasks.sync_campaign_data" etc.) don't match the tasks' real registered
                names (which include the submodule: "app.workers.tasks.sync.sync_campaign_data"),
                so routing-by-name never binds — the queue design is non-functional end-to-end.
Blast radius:   Scheduled data freshness is dead: campaigns never auto-sync from ad platforms,
                daily forecasts and 30-min live predictions never generate, audiences never
                auto-sync on schedule. Everything downstream (pacing, ROAS, dashboards, autopilot
                inputs) runs on stale data that only updates when a user manually triggers a sync.
                Silent — no error, jobs just pile up unconsumed. (Not clearly conversion-caused;
                likely pre-existing queue/infra config, but a live BROKEN state for core features.)
Evidence:       celery_app.py:70 task_default_queue="default"; :101/107/144/187/206/241/252 explicit
                non-default queues; worker commands (3 deploy files) carry no -Q; grep for "-Q" in
                all deploy/compose/railway/start.sh = 0. task_routes keys vs real names mismatch.
Fix:            Simplest: launch the worker with `-Q default,sync,ml,intel,rules` (or drop the
                per-task `options.queue` and route everything to default). Also fix task_routes keys
                to the real dotted names (or remove task_routes). Add a smoke check that beat-
                dispatched tasks are consumed (inspect active_queues vs scheduled queues).
Confirm via:    Enqueue sync_all_campaigns via beat; `celery -A app.workers.celery_app inspect
                active_queues` shows the worker bound only to "default"; the "sync" queue depth
                (redis LLEN) grows without draining.
```

```
FINDING-6-2
Feature:        FEAT-119 / FEAT-164 (CRM sync & attribution writeback — HubSpot/Zoho/Pipedrive)
Status:         BROKEN
Severity:       MEDIUM
Confidence:     HIGH (CONFIRMED)
What is broken: The CRM background-sync feature never runs. app/workers/crm_sync_tasks.py is NOT in
                celery_app.py `include=[...]`, so its @task defs (sync_hubspot_data, sync_zoho_data,
                writeback_hubspot_attribution, writeback_zoho_attribution, run_identity_matching,
                sync_all_crm_connections, run_scheduled_writebacks) are never registered on the
                worker. Its `.delay()` sites (crm_sync_tasks.py:289,294,363,369) would be silent
                no-ops — but they live inside sync_all_crm_connections / run_scheduled_writebacks,
                which are themselves only in a local `CRM_BEAT_SCHEDULE` dict (:434) that is NEVER
                merged into celery_app.conf.beat_schedule. Doubly dead: unregistered AND unscheduled.
Root cause:     Module omitted from `include` and its beat schedule never applied (the confirmed-
                fixed sibling rollups were added to `include`; CRM was not — .coveragerc:26 even
                notes it is "absent from the Celery include").
Blast radius:   No automatic CRM contact sync and no attribution writeback to HubSpot/Zoho/
                Pipedrive. Data flows one way / not at all on schedule. Intersects FINDING-4-3
                (crm_connections duplicate-row 500) and Phase 9 (integrations).
Evidence:       celery_app.py:19-44 include list (no crm_sync_tasks); crm_sync_tasks.py:434
                CRM_BEAT_SCHEDULE defined, never `.update()`d into conf.beat_schedule.
Fix:            Add "app.workers.crm_sync_tasks" to include and merge CRM_BEAT_SCHEDULE into the
                beat schedule (gated behind a flag, like the campaign-builder trio), OR remove the
                module + its FE surface if CRM sync is out of scope for the single client.
Confirm via:    `celery -A app.workers.celery_app inspect registered` → sync_hubspot_data absent.
```

```
FINDING-6-3
Feature:        FEAT-120 / FEAT-121 (legacy standalone Celery apps) + data-retention cleanup, weekly digest
Status:         DEGRADED
Severity:       MEDIUM
Confidence:     HIGH (CONFIRMED)
What is broken: Two standalone Celery apps are entirely dead — never launched, never enqueued:
                app/stratum/workers/data_sync.py (own Celery(), 11 tasks + own beat_schedule) and
                app/stratum/workers/automation_runner.py (aliased "ln", 7 autopilot tasks + own beat).
                No deploy command starts them (grep of compose/railway/start.sh/Makefile = 0) and no
                live code imports/enqueues app.stratum.workers.* (grep = 0). They are the pre-
                conversion execution engine, superseded by the stratum_ai app (apply_actions_queue,
                signal_health_rollup, sync tasks). As dead code this is NEEDS-REMOVAL (LOW), BUT two
                capabilities exist ONLY here with NO live equivalent:
                  - cleanup_old_data (data_sync.py:667, 90-day retention purge) — runs NOWHERE
                  - send_weekly_digest (data_sync.py:648, weekly email digest) — runs NOWHERE
Root cause:     Legacy engine left in tree at conversion; retention/digest never re-homed into
                stratum_ai.
Blast radius:   Data-retention purge is not enforced by any running job (compounds FINDING-2-2,
                where the compliance retention-policy source table also doesn't exist — retention is
                broken end-to-end: no policy table AND no cleanup job). No weekly digest is sent.
                Dead-code confusion risk: two `data_sync.py` files (app/workers vs app/stratum/workers)
                and an "ln" alias for automation_runner invite future mis-edits.
Evidence:       data_sync.py:96 Celery(), :114 beat_schedule, :648 send_weekly_digest, :667
                cleanup_old_data; automation_runner.py beat entries app.stratum.workers.ln.*; no
                launcher/importer anywhere.
Fix:            Delete both standalone apps (and the stratum/workers package) after re-homing
                cleanup_old_data + send_weekly_digest as registered stratum_ai beat tasks if those
                capabilities are wanted; otherwise document their removal.
Confirm via:    grep deploy configs for a launcher of app.stratum.workers → none; no scheduled purge.
```

```
FINDING-6-4
Feature:        FEAT-107 / FEAT-022 (WhatsApp alert dispatched from a rule action)
Status:         BROKEN
Severity:       LOW
Confidence:     HIGH (pre-existing, non-tenant)
What is broken: workers/tasks/rules.py:284 calls send_whatsapp_message.delay(template_name=…,
                to_number=…, variables=…) but the task signature (whatsapp.py:33) requires
                message_id and accepts contact_phone/template_variables — the call omits the required
                message_id and passes unknown kwargs to_number/variables → TypeError at runtime.
Root cause:     Pre-existing arg-contract drift, explicitly flagged in-code (rules.py:279-283) as
                unrelated to the de-tenanting. Reachable only when a Rule with action_type
                "send_alert" + whatsapp config fires.
Blast radius:   A WhatsApp alert rule action crashes instead of sending. Narrow (automation rules
                are a default-off feature, and this specific action path). Recorded for completeness;
                NOT conversion-caused.
Fix:            Correct the call to pass message_id + valid kwargs (or adapt the task to accept a
                template+to_number ad-hoc send).
Confirm via:    Create a send_alert rule with whatsapp; trigger it → TypeError in worker log.
```

## Cross-refs
- 6-1 root cause (task_routes name mismatch) is the FEAT-123 Phase-1 seed — dispositioned here (dead map, no runtime routing).
- 6-2 intersects FINDING-4-3 (CRM connection duplicate crash) and feeds Phase 9 (integrations health).
- 6-3 compounds FINDING-2-2 (retention policy) — the full data-retention story is non-functional.
- The confirmed-fixed registration gaps (apply_actions, rollups, newsletter, audience_auto_sync) are genuine fixes — no regression.

## Phase 6 summary
The *conversion-specific* job risks are CLEAN: task signatures are fully de-tenanted, no consumer dereferences a removed tenant field, and no fan-out iterates a removed tenant set. The real damage is orthogonal-but-live infrastructure: a **queue-binding mismatch that strands core scheduled jobs** (6-1, HIGH — campaign sync/forecasts/predictions/audience-sync never run on schedule), an **unregistered CRM module** (6-2), and **dead legacy Celery apps that took data-retention cleanup and weekly digest down with them** (6-3). One pre-existing non-tenant task-arg bug (6-4). 6-1 and 6-3 are, like Phase 5, exactly the kind of failure a core-flow smoke test misses but a scheduled-job/queue inspection surfaces — reinforcing the need for Phase 13 runtime verification.

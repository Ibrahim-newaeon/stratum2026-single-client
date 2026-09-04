---
name: incident-response
description: Investigate a Stratum single-client incident without performing destructive or production changes.
disable-model-invocation: true
---

1. Establish the affected subsystem, time window, user impact, and last known good state.
2. Collect read-only evidence from logs, metrics, registered routes/workers, configuration names, and recent changes.
3. Check signal freshness, trust-gate state, queues, database health, and external integration failures.
4. Do not use tenant, subscription, licensing, or billing playbooks from other Stratum repositories.
5. Propose containment, recovery, verification, and rollback steps. Ask before any production mutation.

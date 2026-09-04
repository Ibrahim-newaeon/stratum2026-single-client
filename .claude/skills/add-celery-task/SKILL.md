---
name: add-celery-task
description: Add a retry-safe single-client Celery task without reintroducing tenant or billing behavior.
---

1. Read neighboring tasks, worker registration, services, and tests.
2. Keep inputs explicit but do not add tenant identifiers or billing/subscription behavior.
3. Make external mutations idempotent and retries bounded with backoff.
4. Manage database sessions and async resources through established patterns.
5. Preserve structured logging, audit records, and transaction boundaries without exposing secrets or PII.
6. Add tests for success, retry, duplicate delivery, and terminal failure.
7. Confirm worker registration and run focused tests.

---
name: add-platform-integration
description: Add or extend a registered single-client platform integration with secure credentials and fail-closed signal behavior.
---

1. Trace the existing adapter, registry, router, worker, configuration, and test patterns.
2. Keep credentials server-side and encrypted through established storage.
3. Preserve OAuth state or webhook signature checks, idempotency, retries, and auditability.
4. Do not add tenant scope, plans, licensing, subscriptions, Stripe, Paddle, or billing.
5. A sync that writes no metrics must not report success or fresh signal health.
6. Add focused adapter, registration, failure, and data-freshness tests.

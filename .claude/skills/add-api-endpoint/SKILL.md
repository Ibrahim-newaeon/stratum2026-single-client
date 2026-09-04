---
name: add-api-endpoint
description: Add a FastAPI endpoint that follows the single-client architecture and repository validation patterns.
---

1. Read neighboring routes, schemas, services, dependencies, and tests.
2. Define validated request and response models and use established authentication and role dependencies.
3. Keep reusable behavior in a service or domain module.
4. Do not add tenant, subscription, licensing, Stripe, Paddle, or billing fields or checks.
5. Preserve rate limits, auditability, idempotency, transaction ownership, and safe errors.
6. Add focused success, validation, authorization, and failure tests.
7. Run the smallest affected checks, then the relevant backend gate.

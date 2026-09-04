---
paths:
  - "backend/**"
  - "frontend/**"
  - "docs/**"
---

# Single-client boundary

This repository deliberately removed tenancy, subscription tiers, licensing, and payment processing.

- Do not add `tenant_id`, tenant middleware, tenant selectors, tenant-scoped queries, plan gates, subscriptions, Stripe, Paddle, checkout, invoices, or billing webhooks to live code.
- Historical documents and explicit removal tests may mention removed concepts, but they are not implementation examples.
- When porting code from another Stratum repository, remove tenant and billing behavior before adapting the remainder.
- Preserve authentication, roles, trust-gate enforcement, audit logging, idempotency, and data integrity.

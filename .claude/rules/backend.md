---
paths:
  - "backend/**"
---

# Backend rules

- Follow the single-client boundary; tenant and billing concepts are prohibited in live code.
- Keep route transport thin and reusable behavior in services or domain modules.
- Preserve authentication, authorization, audit records, rate limits, idempotency, asynchronous I/O, and transaction ownership.
- Append Alembic migrations. Never rewrite applied history or run destructive database operations without explicit approval.
- Run focused backend tests before the wider affected quality gate.

---
name: db-query-review
description: Review SQLAlchemy or SQL changes for correctness, async safety, performance, and the single-client boundary.
---

1. Confirm the query follows the established async session and transaction pattern.
2. Check authorization, ownership, soft-delete, status, and time-window filters required by the domain.
3. Reject tenant filters or tenant columns in live code; tenancy was removed.
4. Check joins, eager loading, pagination, indexes, null behavior, locking, and N+1 risk.
5. Require append-only migrations and safe backfill/recovery for schema changes.
6. Add or update focused query tests and report evidence.

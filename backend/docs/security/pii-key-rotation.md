# PII Encryption Key Rotation Runbook

## Context

ADs Growth System encrypts PII columns (`User.email`, `User.full_name`, `User.phone`,
`User.totp_secret`, OAuth/CRM access & refresh tokens, etc.) at rest with
Fernet symmetric encryption via `app.core.security.encrypt_pii` /
`decrypt_pii`. As of the single-client conversion (STRAT-SC-001) there is
**exactly one** encryption key for the whole deployment, derived via PBKDF2
from the `PII_ENCRYPTION_KEY` environment variable / `settings.pii_encryption_key`.

The previous per-tenant envelope-encryption scheme (per-tenant DEKs wrapped by
a KEK, `app/core/pii_keys.py`) was removed — it existed to let one tenant's
key rotate/compromise be isolated from another's, which is meaningless for a
single-org deployment. Key rotation is now a whole-database operation.

## When to rotate

- Suspected key compromise (leaked env var, compromised secrets store, departing
  operator with prior access to the value).
- Scheduled rotation per your organization's security policy (e.g. annually).
- Post-incident hardening.

## Rotation procedure

1. **Generate a new key.**
   ```python
   from cryptography.fernet import Fernet
   print(Fernet.generate_key().decode())
   ```
   Store the new value in your secrets manager; do not commit it to source
   control or log it.

2. **Take a database backup.** Rotation rewrites every encrypted column;
   a restorable snapshot is mandatory before starting.

3. **Run the re-encryption script** (see "Follow-up: build the rotation
   script" below) with both the OLD and NEW keys available to the process,
   e.g.:
   ```bash
   OLD_PII_ENCRYPTION_KEY=<current key> \
   NEW_PII_ENCRYPTION_KEY=<newly generated key> \
   python scripts/rotate_pii_key.py --batch-size 500
   ```
   The script must:
   - Iterate every table/column encrypted via `EncryptedString`
     (`app/db/types.py`) or manual `encrypt_pii` calls (see "Encrypted
     columns inventory" below).
   - For each row: decrypt with the OLD key, re-encrypt with the NEW key,
     write back in the same transaction as the read (read-modify-write per
     row or small batch, not a single giant transaction).
   - Checkpoint progress (e.g. a `rotation_checkpoint` table or a
     `--resume-from-id` flag) so an interrupted run can resume without
     re-processing already-rotated rows.
   - Run with the app in a maintenance/read-only mode, or accept that rows
     written *during* the rotation window need a second pass (simplest: put
     the app in maintenance mode for the duration).

4. **Swap the environment variable.** Set `PII_ENCRYPTION_KEY` (root `.env` /
   deployment secret) to the NEW key value everywhere the app and workers
   read config from.

5. **Restart all processes** (API, Celery worker, Celery beat) so they pick
   up the new key. There is no more per-tenant key cache to warm — the
   single key derives synchronously on first use.

6. **Verify.** The app's startup self-test (`app/main.py` lifespan) already
   asserts the configured key can encrypt+decrypt a probe value before
   accepting traffic; a clean boot is the primary signal rotation succeeded.
   Spot-check a handful of real rows (e.g. log in as a user, confirm profile
   data renders) to confirm the re-encryption pass covered production data.

7. **Discard the OLD key** from secrets storage only after you've confirmed
   no unrotated ciphertext remains (i.e. the re-encryption script completed
   and reported zero remaining rows on the old key).

## Encrypted columns inventory (as of STRAT-SC-001)

- `User.email`, `User.full_name`, `User.phone`, `User.totp_secret`
- OAuth connection tokens: `access_token_encrypted` / `refresh_token_encrypted`
  (console/integrations OAuth connections)
- CRM client tokens: `access_token_enc` / `refresh_token_enc`
  (HubSpot, Pipedrive, Zoho clients in `app/services/crm/`)
- Audience-sync platform tokens (`app/models/audience_sync.py`)
- Any column typed `EncryptedString` (`app/db/types.py`) — grep
  `EncryptedString` in `app/models/` for the authoritative, current list at
  rotation time.

## Follow-up: build the rotation script (not built yet)

`scripts/rotate_pii_key.py` is intentionally **not implemented** as part of
this runbook (YAGNI until the first real rotation is needed). When it's
built, it should:

- Accept `OLD_PII_ENCRYPTION_KEY` / `NEW_PII_ENCRYPTION_KEY` (or CLI flags)
  rather than relying on `settings.pii_encryption_key` alone, since both keys
  must be available simultaneously during the migration window.
- Reuse the same PBKDF2 derivation as `app.core.security._get_fernet_key`
  (same salt, iteration count) so old/new `Fernet` instances are constructed
  identically to how the app builds them.
- Process rows in batches with checkpointing (see step 3 above), and be
  idempotent/resumable.
- Emit a summary (rows scanned, rows rotated, rows already-plaintext /
  legacy-format skipped) for the operator running it.

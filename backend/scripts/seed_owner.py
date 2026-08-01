#!/usr/bin/env python3
"""
ADs Growth System - Owner Seed Script

Creates the Organization singleton (id=1) and the owner user for this
single-client deployment. STRAT-SC-001: replaces the old per-tenant
seed_superadmin.py — there is exactly one organization now, so this script
no longer creates or looks up a `tenants` row.

Usage:
    docker compose exec api python scripts/seed_owner.py

Or from the backend folder:
    python scripts/seed_owner.py
"""

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.security import encrypt_pii, get_password_hash, hash_pii_for_lookup

# =============================================================================
# Owner Configuration (read from env vars with fallbacks for dev only)
# =============================================================================

# SECURITY: These MUST be provided via environment variables.
# The script will fail fast if they are not set.
SUPERADMIN_EMAIL = os.environ.get("SUPERADMIN_EMAIL")
SUPERADMIN_PASSWORD = os.environ.get("SUPERADMIN_PASSWORD")
SUPERADMIN_NAME = os.environ.get("SUPERADMIN_NAME", "Platform Owner")
# Organization identity (single-client: there is exactly one org, id=1).
ORG_NAME = os.environ.get("SUPERADMIN_TENANT_NAME", "ADs Growth System")
ORG_SLUG = os.environ.get("SUPERADMIN_TENANT_SLUG", "stratum-ai")


class OwnerSeedConfigError(RuntimeError):
    """Raised when the owner-seed env vars are missing or invalid.

    A normal exception — NOT sys.exit — so importing this module is
    side-effect-free. The app lifespan imports ``create_owner`` and wraps it in
    a best-effort ``except Exception``; a bare ``SystemExit`` from a module-level
    ``sys.exit`` would escape that guard (SystemExit is not an Exception) and
    crash startup when the env vars are unset (STRAT-SC-001 fix 13-1). The CLI
    entrypoint still fail-fasts by catching this and exiting.
    """


def _validate_owner_config() -> None:
    """Validate SUPERADMIN_* env vars; raise OwnerSeedConfigError if unusable."""
    if not SUPERADMIN_EMAIL or not SUPERADMIN_PASSWORD:
        raise OwnerSeedConfigError(
            "SUPERADMIN_EMAIL and SUPERADMIN_PASSWORD environment variables are required."
        )
    if len(SUPERADMIN_PASSWORD) < 16:
        raise OwnerSeedConfigError(
            "SUPERADMIN_PASSWORD must be at least 16 characters."
        )


async def create_owner():
    """Create the Organization singleton and owner user using raw SQL."""

    _validate_owner_config()

    # Create async engine
    engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False,
    )

    try:
        async with engine.begin() as conn:
            now = datetime.now(UTC)

            # Step 1: Ensure the Organization singleton (id=1) exists.
            result = await conn.execute(
                text("SELECT id, name FROM organization WHERE id = 1")
            )
            org = result.fetchone()

            if not org:
                print(f"Creating organization: {ORG_NAME}")
                await conn.execute(
                    text("""
                        INSERT INTO organization (
                            id, name, slug, branding, settings, feature_flags,
                            enforcement_mode, onboarding_state, is_onboarded,
                            created_at, updated_at
                        ) VALUES (
                            1, :name, :slug, '{}', '{}', '{}',
                            'advisory', '{}', false,
                            :now, :now
                        )
                    """),
                    {"name": ORG_NAME, "slug": ORG_SLUG, "now": now},
                )
                print("  Organization ID: 1")
            else:
                print(f"Using existing organization: {org[1]} (ID: {org[0]})")

            # Step 2: Check if owner already exists
            email_hash = hash_pii_for_lookup(SUPERADMIN_EMAIL.lower())
            result = await conn.execute(
                text(
                    "SELECT id, role, is_active, is_verified FROM users WHERE email_hash = :email_hash"
                ),
                {"email_hash": email_hash},
            )
            existing = result.fetchone()

            if existing:
                password_hash = get_password_hash(SUPERADMIN_PASSWORD)
                print(f"Owner already exists: {SUPERADMIN_EMAIL}")
                print(f"  User ID: {existing[0]}")
                print("  Updating password and ensuring active/verified...")
                await conn.execute(
                    text(
                        "UPDATE users SET password_hash = :password_hash, role = 'owner', "
                        "is_active = true, is_verified = true WHERE email_hash = :email_hash"
                    ),
                    {"password_hash": password_hash, "email_hash": email_hash},
                )
                print("  Password updated successfully!")
                return

            # Step 3: Create owner user using raw SQL
            print(f"\nCreating owner user: {SUPERADMIN_EMAIL}")
            encrypted_email = encrypt_pii(SUPERADMIN_EMAIL.lower())
            encrypted_name = encrypt_pii(SUPERADMIN_NAME)
            password_hash = get_password_hash(SUPERADMIN_PASSWORD)

            result = await conn.execute(
                text("""
                    INSERT INTO users (
                        email, email_hash, password_hash, full_name,
                        role, permissions, is_active, is_verified, is_protected,
                        locale, timezone, preferences,
                        consent_marketing, consent_analytics,
                        totp_enabled, failed_totp_attempts, user_type,
                        created_at, updated_at, is_deleted
                    ) VALUES (
                        :email, :email_hash, :password_hash, :full_name,
                        'owner', '{}', true, true, false,
                        'en', 'UTC', '{}',
                        false, true,
                        false, 0, 'agency',
                        :now, :now, false
                    )
                    RETURNING id
                """),
                {
                    "email": encrypted_email,
                    "email_hash": email_hash,
                    "password_hash": password_hash,
                    "full_name": encrypted_name,
                    "now": now,
                },
            )
            user_id = result.fetchone()[0]

            print("\n" + "=" * 50)
            print("OWNER CREATED SUCCESSFULLY")
            print("=" * 50)
            print(f"  Email:    {SUPERADMIN_EMAIL}")
            print("  Password:  [set via SUPERADMIN_PASSWORD env var]")
            print("  Role:     owner")
            print(f"  Organization: {ORG_NAME}")
            print(f"  User ID:  {user_id}")
            print("=" * 50)
            print("\nYou can now log in at /login with these credentials.")

    except Exception as e:
        print(f"\nError creating owner: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("ADs Growth System - Owner Seed Script")
    print("=" * 50 + "\n")

    try:
        asyncio.run(create_owner())
    except OwnerSeedConfigError as exc:
        print(f"ERROR: {exc}")
        print(
            "Example: SUPERADMIN_EMAIL=admin@example.com "
            "SUPERADMIN_PASSWORD=$(openssl rand -base64 32) python scripts/seed_owner.py"
        )
        sys.exit(1)

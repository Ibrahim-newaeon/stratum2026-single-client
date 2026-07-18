"""add single-row guards + crm provider unique constraint

Adds the DB-level one-row invariants the single-client conversion left off
(STRAT-SC-001 fixes 4-1 / 4-2 / 4-3):

- ``enforcement_settings`` — unique index on the constant expression ``(true)``
  so at most one settings row can exist. The autopilot emergency-stop flag is
  read with an unordered ``.first()``; with a guaranteed single row that read is
  deterministic (operator freeze and the execution-path read can't disagree).
- ``organization_onboarding`` — same single-row guard, so concurrent first-loads
  cannot create duplicate rows that make the ``.limit(1)`` read flap.
- ``crm_connections`` — ``UNIQUE(provider)`` so provider-keyed get-or-create can
  never yield a duplicate row that raises ``MultipleResultsFound`` and 500s.

Existing duplicate rows are collapsed to one (by ctid; per-provider for CRM)
before the constraints are added, so the migration is safe on a populated DB.

Revision ID: d1e2f3a4b5c6
Revises: c8d2e5f7a1b3
Create Date: 2026-07-18 01:00:00.000000+00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c8d2e5f7a1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- enforcement_settings: collapse to a single row ---
    op.execute("""
        DELETE FROM enforcement_settings a
        USING enforcement_settings b
        WHERE a.ctid < b.ctid
        """)
    op.create_index(
        "uq_enforcement_settings_singleton",
        "enforcement_settings",
        [sa.text("(true)")],
        unique=True,
    )

    # --- organization_onboarding: collapse to a single row ---
    op.execute("""
        DELETE FROM organization_onboarding a
        USING organization_onboarding b
        WHERE a.ctid < b.ctid
        """)
    op.create_index(
        "uq_organization_onboarding_singleton",
        "organization_onboarding",
        [sa.text("(true)")],
        unique=True,
    )

    # --- crm_connections: one row per provider ---
    op.execute("""
        DELETE FROM crm_connections a
        USING crm_connections b
        WHERE a.provider = b.provider AND a.ctid < b.ctid
        """)
    # The old non-unique index is superseded by the unique constraint's index.
    op.drop_index("ix_crm_connections_provider", table_name="crm_connections")
    op.create_unique_constraint(
        "uq_crm_connections_provider", "crm_connections", ["provider"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_crm_connections_provider", "crm_connections", type_="unique")
    op.create_index(
        "ix_crm_connections_provider", "crm_connections", ["provider"], unique=False
    )
    op.drop_index(
        "uq_organization_onboarding_singleton",
        table_name="organization_onboarding",
    )
    op.drop_index(
        "uq_enforcement_settings_singleton", table_name="enforcement_settings"
    )

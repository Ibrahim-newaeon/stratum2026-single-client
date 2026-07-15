"""rename tenant-prefixed tables to single-client names

Renames the last three tenant_-prefixed tables left over from the
multi-tenant -> single-client conversion (STRAT-SC-001 / spec-audit P2-11):

- tenant_onboarding            -> organization_onboarding
- tenant_enforcement_settings  -> enforcement_settings
- tenant_enforcement_rules     -> enforcement_rules

PostgreSQL's ALTER TABLE ... RENAME TO does NOT rename dependent
constraints, indexes, or sequences, so those are renamed explicitly to
keep DB object names in sync with the models' naming convention.

Revision ID: b7e3f4a9c2d1
Revises: 12a656044fcc
Create Date: 2026-07-15 10:15:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e3f4a9c2d1"
down_revision: Union[str, None] = "12a656044fcc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The FK on tenant_enforcement_rules(settings_id) was declared as
# fk_tenant_enforcement_rules_settings_id_tenant_enforcement_settings
# (68 chars) which exceeds PostgreSQL's 63-char identifier limit, so
# SQLAlchemy created it with a truncated md5-suffixed name. Verified
# against the DDL emitted by the initial migration (12a656044fcc):
_OLD_RULES_FK = "fk_tenant_enforcement_rules_settings_id_tenant_enforcem_be06"
_NEW_RULES_FK = "fk_enforcement_rules_settings_id_enforcement_settings"

# Rename via lookup instead of hardcoding the truncated name, in case a
# different SQLAlchemy version produced a different hash suffix.
_RENAME_RULES_FK_SQL = """
DO $$
DECLARE
    fk_name text;
BEGIN
    SELECT conname INTO STRICT fk_name
    FROM pg_constraint
    WHERE conrelid = '{table}'::regclass
      AND contype = 'f';
    EXECUTE format(
        'ALTER TABLE {table} RENAME CONSTRAINT %I TO %I',
        fk_name, '{new_name}'
    );
END $$;
"""


def upgrade() -> None:
    # --- tenant_onboarding -> organization_onboarding ---
    op.rename_table("tenant_onboarding", "organization_onboarding")
    # serial PK sequence keeps its old name after a table rename
    op.execute(
        "ALTER SEQUENCE IF EXISTS tenant_onboarding_id_seq "
        "RENAME TO organization_onboarding_id_seq"
    )
    # renaming a PK/unique constraint also renames its backing index
    op.execute(
        "ALTER TABLE organization_onboarding RENAME CONSTRAINT "
        "pk_tenant_onboarding TO pk_organization_onboarding"
    )
    op.execute(
        "ALTER TABLE organization_onboarding RENAME CONSTRAINT "
        "fk_tenant_onboarding_completed_by_user_id_users "
        "TO fk_organization_onboarding_completed_by_user_id_users"
    )
    op.execute(
        "ALTER INDEX ix_tenant_onboarding_status "
        "RENAME TO ix_organization_onboarding_status"
    )
    op.execute(
        "ALTER INDEX ix_tenant_onboarding_completed_by_user_id "
        "RENAME TO ix_organization_onboarding_completed_by_user_id"
    )

    # --- tenant_enforcement_settings -> enforcement_settings ---
    op.rename_table("tenant_enforcement_settings", "enforcement_settings")
    op.execute(
        "ALTER TABLE enforcement_settings RENAME CONSTRAINT "
        "pk_tenant_enforcement_settings TO pk_enforcement_settings"
    )

    # --- tenant_enforcement_rules -> enforcement_rules ---
    op.rename_table("tenant_enforcement_rules", "enforcement_rules")
    op.execute(
        "ALTER TABLE enforcement_rules RENAME CONSTRAINT "
        "pk_tenant_enforcement_rules TO pk_enforcement_rules"
    )
    op.execute(
        _RENAME_RULES_FK_SQL.format(table="enforcement_rules", new_name=_NEW_RULES_FK)
    )
    op.execute(
        "ALTER INDEX ix_tenant_enforcement_rules_settings_id "
        "RENAME TO ix_enforcement_rules_settings_id"
    )
    # uq_rule_id carries no table prefix — unchanged.


def downgrade() -> None:
    # --- enforcement_rules -> tenant_enforcement_rules ---
    op.execute(
        "ALTER INDEX ix_enforcement_rules_settings_id "
        "RENAME TO ix_tenant_enforcement_rules_settings_id"
    )
    op.execute(
        _RENAME_RULES_FK_SQL.format(table="enforcement_rules", new_name=_OLD_RULES_FK)
    )
    op.execute(
        "ALTER TABLE enforcement_rules RENAME CONSTRAINT "
        "pk_enforcement_rules TO pk_tenant_enforcement_rules"
    )
    op.rename_table("enforcement_rules", "tenant_enforcement_rules")

    # --- enforcement_settings -> tenant_enforcement_settings ---
    op.execute(
        "ALTER TABLE enforcement_settings RENAME CONSTRAINT "
        "pk_enforcement_settings TO pk_tenant_enforcement_settings"
    )
    op.rename_table("enforcement_settings", "tenant_enforcement_settings")

    # --- organization_onboarding -> tenant_onboarding ---
    op.execute(
        "ALTER INDEX ix_organization_onboarding_completed_by_user_id "
        "RENAME TO ix_tenant_onboarding_completed_by_user_id"
    )
    op.execute(
        "ALTER INDEX ix_organization_onboarding_status "
        "RENAME TO ix_tenant_onboarding_status"
    )
    op.execute(
        "ALTER TABLE organization_onboarding RENAME CONSTRAINT "
        "fk_organization_onboarding_completed_by_user_id_users "
        "TO fk_tenant_onboarding_completed_by_user_id_users"
    )
    op.execute(
        "ALTER TABLE organization_onboarding RENAME CONSTRAINT "
        "pk_organization_onboarding TO pk_tenant_onboarding"
    )
    op.execute(
        "ALTER SEQUENCE IF EXISTS organization_onboarding_id_seq "
        "RENAME TO tenant_onboarding_id_seq"
    )
    op.rename_table("organization_onboarding", "tenant_onboarding")

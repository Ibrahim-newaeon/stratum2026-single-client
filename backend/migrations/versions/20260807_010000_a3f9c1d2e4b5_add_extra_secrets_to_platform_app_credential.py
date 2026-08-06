"""Add extra_secrets column to platform_app_credential.

Holds a JSON dict of platform-specific extra fields (WhatsApp webhook
verify token / app secret, Meta pixel + ad-account ids, Google login
customer id, …) encrypted as a single blob. Hand-written: autogenerate
was rejected because it picked up unrelated model/DB drift.

Revision ID: a3f9c1d2e4b5
Revises: d1e2f3a4b5c6
Create Date: 2026-08-07 01:00:00+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

# revision identifiers, used by Alembic.
revision: str = "a3f9c1d2e4b5"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_app_credential",
        sa.Column(
            "extra_secrets",
            app.db.types.EncryptedString(length=4096),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("platform_app_credential", "extra_secrets")

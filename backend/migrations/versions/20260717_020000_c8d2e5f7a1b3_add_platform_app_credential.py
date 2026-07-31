"""Add platform_app_credential table (per-deployment OAuth app credentials).

Revision ID: c8d2e5f7a1b3
Revises: b7e3f4a9c2d1
Create Date: 2026-07-17 02:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
import app.db.types

# revision identifiers, used by Alembic.
revision: str = "c8d2e5f7a1b3"
down_revision: Union[str, None] = "b7e3f4a9c2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_app_credential",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column(
            "client_secret", app.db.types.EncryptedString(length=1024), nullable=False
        ),
        sa.Column(
            "developer_token", app.db.types.EncryptedString(length=1024), nullable=True
        ),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_platform_app_credential_platform",
        "platform_app_credential",
        ["platform"],
    )


def downgrade() -> None:
    op.drop_table("platform_app_credential")

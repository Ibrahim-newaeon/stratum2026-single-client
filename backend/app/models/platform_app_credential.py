# =============================================================================
# Stratum AI - Platform App Credentials
# =============================================================================
"""
Per-deployment OAuth *application* credentials for ad platforms (Meta app ID/
secret, Google Ads client ID/secret + developer token, TikTok, Snapchat).

Black-box deployment model: the customer's owner enters these once via the
Settings → Integrations panel; they are resolved DB-first with env-var
fallback (see app/services/oauth/credentials.py). Secrets are Fernet-
encrypted at rest via the EncryptedString column type and are never returned
by any API after save.
"""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin
from app.db.types import EncryptedString


class PlatformAppCredential(Base, TimestampMixin):
    __tablename__ = "platform_app_credential"
    __table_args__ = (
        UniqueConstraint("platform", name="uq_platform_app_credential_platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret: Mapped[str] = mapped_column(EncryptedString(1024), nullable=False)
    developer_token: Mapped[str | None] = mapped_column(
        EncryptedString(1024), nullable=True
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

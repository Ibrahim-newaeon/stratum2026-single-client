"""PlatformAppCredential: encrypted-at-rest secrets, one row per platform."""

from app.db.types import EncryptedString
from app.models.platform_app_credential import PlatformAppCredential


def test_secret_columns_are_encrypted_types() -> None:
    cols = PlatformAppCredential.__table__.columns
    assert isinstance(cols["client_secret"].type, EncryptedString)
    assert isinstance(cols["developer_token"].type, EncryptedString)
    # client_id is public (appears in OAuth URLs) — plaintext by design.
    assert not isinstance(cols["client_id"].type, EncryptedString)


def test_platform_unique_constraint() -> None:
    constraints = {
        c.name for c in PlatformAppCredential.__table__.constraints if c.name
    }
    assert "uq_platform_app_credential_platform" in constraints


def test_encrypted_string_round_trip() -> None:
    enc = EncryptedString(1024)
    stored = enc.process_bind_param("super-secret-value", dialect=None)
    assert stored and stored != "super-secret-value"
    assert enc.process_result_value(stored, dialect=None) == "super-secret-value"

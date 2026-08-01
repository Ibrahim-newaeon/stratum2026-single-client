# =============================================================================
# ADs Growth System - PII Encryption Unit Tests [STRAT-SC-001]
# =============================================================================
"""
Covers the single-key PII encryption primitives in ``app.core.security``.

Supersedes the old per-tenant DEK envelope tests (``test_pii_keys.py``,
AUTH-05) now that the single-client conversion dropped per-tenant key
provisioning: there is exactly one Fernet key, derived once from
``settings.pii_encryption_key``, for the whole process.
"""

import pytest

from app.core.security import decrypt_pii, encrypt_pii

pytestmark = pytest.mark.unit


def test_fernet_key_derivation_is_stable():
    """The single global Fernet key derives deterministically (fix 12-2).

    The per-tenant key-provisioning tests were dropped with the multi-tenant
    model; this covers the surviving single-key derivation path — it must be
    stable across calls so data encrypted earlier stays decryptable.
    """
    from app.core.security import _get_fernet_key

    assert _get_fernet_key() == _get_fernet_key()


def test_encrypt_decrypt_roundtrips():
    ct = encrypt_pii("alice@example.com")
    assert ct != "alice@example.com"
    assert decrypt_pii(ct) == "alice@example.com"


def test_encrypt_is_not_deterministic_but_decrypts_consistently():
    # Fernet includes a random IV, so two encryptions of the same plaintext
    # produce different ciphertext, but both must decrypt to the same value.
    ct1 = encrypt_pii("secret")
    ct2 = encrypt_pii("secret")
    assert ct1 != ct2
    assert decrypt_pii(ct1) == decrypt_pii(ct2) == "secret"


def test_empty_string_passthrough():
    assert encrypt_pii("") == ""
    assert decrypt_pii("") == ""


def test_corrupted_ciphertext_raises():
    with pytest.raises(ValueError):
        decrypt_pii("not-valid-ciphertext")


def test_encrypt_pii_signature_has_no_tenant_param():
    # Single-key model: encrypt_pii/decrypt_pii take only the value.
    import inspect

    assert list(inspect.signature(encrypt_pii).parameters) == ["plaintext"]
    assert list(inspect.signature(decrypt_pii).parameters) == ["ciphertext"]

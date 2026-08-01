# =============================================================================
# ADs Growth System - Secrets-at-Rest Tests
# =============================================================================
"""
Tests for P0-6:
- Slack webhook URL is encrypted at rest (EncryptedString).

NOTE (STRAT-SC-001 / Task A1): the license HMAC signing secret tests that
used to live here (``app.services.tenant.licensing``) were removed —
``services/tenant/`` imported the now-deleted tier core module and was
itself deleted wholesale in Task A3.
"""

from app.db.types import EncryptedString


# ---------------------------------------------------------------------------
# EncryptedString
# ---------------------------------------------------------------------------
def test_encrypted_string_round_trips():
    col = EncryptedString()
    plaintext = "https://hooks.slack.com/services/T000/B000/XXXXXXXX"

    stored = col.process_bind_param(plaintext, None)
    assert stored is not None
    assert stored != plaintext  # actually encrypted at rest

    loaded = col.process_result_value(stored, None)
    assert loaded == plaintext


def test_encrypted_string_reads_legacy_plaintext():
    """Rows written before encryption must still read (graceful fallback)."""
    col = EncryptedString()
    legacy = "https://hooks.slack.com/legacy-plaintext"
    assert col.process_result_value(legacy, None) == legacy


def test_encrypted_string_handles_none():
    col = EncryptedString()
    assert col.process_bind_param(None, None) is None
    assert col.process_result_value(None, None) is None

# =============================================================================
# ADs Growth System - De-namespaced cache key round-trip test [STRAT-SC-001, spec §10]
# =============================================================================
"""
Proves the CDP profile cache keys carry no tenant segment (single-org
conversion) and that reads hit writes through the real cache implementation.

``app.api.v1.endpoints.cdp.ProfileCache`` is an in-process OrderedDict cache
(no Redis involved) — this test exercises its actual key-builder methods
(``_make_key`` / ``_make_lookup_key``) rather than a standalone module-level
function, since that's the real shape of the code (adjusted from the plan's
generic template to match).
"""

import pytest

from app.api.v1.endpoints.cdp import ProfileCache

pytestmark = pytest.mark.unit


def test_profile_cache_key_has_no_tenant_segment() -> None:
    cache = ProfileCache()
    key = cache._make_key("42")
    assert "tenant" not in key
    assert key == "profile:42"


def test_lookup_cache_key_has_no_tenant_segment() -> None:
    cache = ProfileCache()
    key = cache._make_lookup_key("email", "abc123")
    assert "tenant" not in key
    assert key == "lookup:email:abc123"


def test_profile_cache_roundtrip_reads_hit_writes() -> None:
    cache = ProfileCache()
    cache.set("42", {"id": "42", "name": "x"})
    assert cache.get("42") == {"id": "42", "name": "x"}


def test_lookup_cache_roundtrip_reads_hit_writes() -> None:
    cache = ProfileCache()
    cache.set_by_lookup("email", "abc123", {"id": "42"})
    assert cache.get_by_lookup("email", "abc123") == {"id": "42"}

"""PlatformSelectionRequest must allow an empty list (soft-gate onboarding)."""

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.onboarding import PlatformSelectionRequest


def test_empty_platform_list_is_valid() -> None:
    req = PlatformSelectionRequest(platforms=[])
    assert req.platforms == []


def test_platform_names_still_validated() -> None:
    with pytest.raises(ValidationError):
        PlatformSelectionRequest(platforms=["myspace"])


def test_platform_names_lowercased() -> None:
    req = PlatformSelectionRequest(platforms=["Meta", "google"])
    assert req.platforms == ["meta", "google"]

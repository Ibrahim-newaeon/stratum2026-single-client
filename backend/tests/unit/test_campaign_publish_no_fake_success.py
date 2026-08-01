# =============================================================================
# ADs Growth System - Campaign Publish Must Not Fabricate Success
# =============================================================================
"""
Regression tests for the publish path behind the feature flag.

test_drip_campaign_publish_shelved.py covers the gate: with
``enable_campaign_publish`` off, the endpoint 503s. It does not cover what
happens once someone turns the flag on — and that was the dangerous part.

Both the endpoint and the Celery task used to synthesise a campaign id, set
DraftStatus.PUBLISHED, and write PublishResult.SUCCESS into CampaignPublishLog
without making a single network call. Enabling the flag to smoke-test produced
green checkmarks, no ads, and an audit table full of fiction.

These tests pin the honest behaviour: refuse, record nothing as succeeded, and
leave the draft publishable for when a real adapter lands.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.campaign_builder import publish_campaign_draft
from app.models.campaign_builder import DraftStatus, PublishResult
from app.workers.campaign_builder_tasks import publish_campaign


def _approved_draft():
    """A draft that passes every validation the endpoint performs."""
    return SimpleNamespace(
        status=DraftStatus.APPROVED,
        platform="meta",
        published_at=None,
        platform_campaign_id=None,
        draft_json={"campaign": {"budget": {"amount": 10}}},
        ad_account=SimpleNamespace(
            daily_budget_cap=None, platform_account_id="act_1"
        ),
    )


def _db_returning(obj):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = obj
    db.execute.return_value = result
    return db


# --- Endpoint ---


async def test_publish_endpoint_refuses_with_501():
    """A fully valid, approved draft is still refused — there is no adapter."""
    db = _db_returning(_approved_draft())

    with pytest.raises(HTTPException) as exc:
        await publish_campaign_draft(draft_id="00000000-0000-0000-0000-000000000001", db=db)

    assert exc.value.status_code == 501
    assert "not implemented" in str(exc.value.detail).lower()


async def test_publish_endpoint_leaves_draft_approved_and_unpublished():
    """The draft must stay publishable, and must not claim to be published."""
    draft = _approved_draft()
    db = _db_returning(draft)

    with pytest.raises(HTTPException):
        await publish_campaign_draft(draft_id="00000000-0000-0000-0000-000000000001", db=db)

    assert draft.status is DraftStatus.APPROVED, "draft was mutated toward published"
    assert draft.published_at is None, "published_at was stamped without a platform call"
    assert draft.platform_campaign_id is None, "a campaign id was synthesised"
    db.commit.assert_not_awaited()


async def test_publish_endpoint_writes_no_publish_log():
    """Nothing was attempted, so nothing should be recorded as attempted."""
    db = _db_returning(_approved_draft())

    with pytest.raises(HTTPException):
        await publish_campaign_draft(draft_id="00000000-0000-0000-0000-000000000001", db=db)

    db.add.assert_not_called()


async def test_publish_endpoint_still_validates_before_refusing():
    """The 501 must not mask real validation — a missing draft is still a 404."""
    db = _db_returning(None)

    with pytest.raises(HTTPException) as exc:
        await publish_campaign_draft(draft_id="00000000-0000-0000-0000-000000000001", db=db)

    assert exc.value.status_code == 404


# --- Celery task ---


def test_publish_task_records_failure_not_success(monkeypatch):
    """The task must mark FAILURE, not the SUCCESS it used to write blind."""
    draft = SimpleNamespace(
        status=DraftStatus.PUBLISHING,
        platform="meta",
        ad_account_id="acc",
        published_at=None,
        platform_campaign_id=None,
        draft_json={},
    )
    log = SimpleNamespace(
        result_status=None,
        error_message=None,
        platform_campaign_id=None,
        response_json=None,
    )
    connection = SimpleNamespace(status=__import__(
        "app.models.campaign_builder", fromlist=["ConnectionStatus"]
    ).ConnectionStatus.CONNECTED)

    # execute() is called for draft, log, ad_account, connection in that order.
    returns = [draft, log, SimpleNamespace(id="acc"), connection]

    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)

    def _execute(*_a, **_kw):
        r = MagicMock()
        r.scalar_one_or_none.return_value = returns.pop(0)
        return r

    db.execute.side_effect = _execute
    monkeypatch.setattr(
        "app.workers.campaign_builder_tasks.SessionLocal", lambda: db
    )

    # bind=True, so __wrapped__ already has `self` bound to the task instance.
    # The NotImplementedError branch must not call self.retry at all — retrying
    # cannot make an unimplemented adapter exist — so leaving the real retry in
    # place is itself part of the assertion: if it fires, Celery raises Retry
    # and the test fails.
    result = publish_campaign.__wrapped__(
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    )

    assert result["status"] == "error"
    assert log.result_status is PublishResult.FAILURE
    assert draft.status is DraftStatus.FAILED
    assert draft.platform_campaign_id is None, "a campaign id was synthesised"
    assert log.platform_campaign_id is None

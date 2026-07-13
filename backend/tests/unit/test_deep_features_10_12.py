# =============================================================================
# Stratum AI - Deep Endpoint Tests for Features 10, 11, 12
# =============================================================================
"""
Deep endpoint tests exercising the FULL request/response cycle via
httpx.AsyncClient, going through real middleware (JWT decode, tenant
extraction) while mocking services/DB at the endpoint handler level.

Feature 10: WhatsApp Integration
Feature 11: Payments (Stripe)
Feature 12: Multi-tenancy
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.conftest import (
    make_auth_headers,
    make_scalar_result,
    make_scalars_result,
)

# =============================================================================
# Helper: mock ORM objects
# =============================================================================


def _mock_contact(**overrides):
    """Build a mock WhatsApp contact ORM object."""
    defaults = dict(
        id=1,
        tenant_id=1,
        user_id=1,
        phone_number="+15551234567",
        country_code="US",
        display_name="John Doe",
        is_verified=False,
        opt_in_status="pending",
        wa_id=None,
        profile_name=None,
        message_count=0,
        last_message_at=None,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _mock_template(**overrides):
    """Build a mock WhatsApp template ORM object."""
    defaults = dict(
        id=1,
        tenant_id=1,
        name="welcome_template",
        language="en",
        category="marketing",
        body_text="Hello {{1}}",
        status="approved",
        usage_count=10,
        meta_template_id="meta_123",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _mock_message(**overrides):
    """Build a mock WhatsApp message ORM object."""
    defaults = dict(
        id=1,
        tenant_id=1,
        contact_id=1,
        direction="outbound",
        message_type="template",
        status="pending",
        content="Hello",
        template_name="welcome_template",
        template_variables={},
        media_url=None,
        sent_at=None,
        delivered_at=None,
        read_at=None,
        scheduled_at=None,
        wamid=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _mock_tenant(**overrides):
    """Build a mock Tenant ORM object."""
    defaults = dict(
        id=1,
        name="Acme Inc",
        slug="acme-inc",
        domain="acme.com",
        plan="professional",
        plan_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        max_users=25,
        max_campaigns=200,
        settings={"currency": "USD", "timezone": "UTC"},
        feature_flags={"whatsapp": True},
        stripe_customer_id="cus_test_123",
        is_deleted=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    obj = MagicMock()
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


# =============================================================================
# FEATURE 10 - WhatsApp Integration
# =============================================================================


class TestWhatsAppContacts:
    """Tests for WhatsApp contact endpoints."""

    # ── No auth → 401/403 ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_list_contacts_no_auth(self, api_client):
        """GET /whatsapp/contacts without auth returns 401/403."""
        resp = await api_client.get("/api/v1/whatsapp/contacts")
        assert resp.status_code in (401, 403)

    # ── Happy path: list contacts ──────────────────────────────────────
    @pytest.mark.asyncio
    async def test_list_contacts_happy_path(self, api_client, mock_db, admin_headers):
        """GET /whatsapp/contacts returns paginated contacts."""
        contacts = [_mock_contact(id=i) for i in range(1, 3)]

        # First call: count query; second call: data query
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        data_result = make_scalars_result(contacts)

        mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

        resp = await api_client.get("/api/v1/whatsapp/contacts", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 2

    # ── Create contact: happy path ─────────────────────────────────────
    @pytest.mark.asyncio
    async def test_create_contact_happy_path(self, api_client, mock_db, admin_headers):
        """POST /whatsapp/contacts creates a new contact."""
        # First execute: duplicate check returns None
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=dup_result)

        new_contact = _mock_contact(id=5, phone_number="+15559999999")
        mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

        # After refresh, the handler calls model_validate on the contact obj.
        # The 'contact' local var is what was db.add()'d. We mock refresh to
        # set attributes on whatever was passed to db.add().
        def _refresh_side_effect(obj):
            for attr in (
                "id",
                "phone_number",
                "country_code",
                "display_name",
                "is_verified",
                "opt_in_status",
                "wa_id",
                "profile_name",
                "message_count",
                "last_message_at",
                "created_at",
            ):
                setattr(obj, attr, getattr(new_contact, attr))

        mock_db.refresh = AsyncMock(side_effect=_refresh_side_effect)

        payload = {
            "phone_number": "+15559999999",
            "country_code": "US",
            "display_name": "Jane Doe",
        }
        resp = await api_client.post(
            "/api/v1/whatsapp/contacts", json=payload, headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["phone_number"] == "+15559999999"

    # ── Create contact: duplicate → 400 ────────────────────────────────
    @pytest.mark.asyncio
    async def test_create_contact_duplicate(self, api_client, mock_db, admin_headers):
        """POST /whatsapp/contacts with existing phone → 400."""
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = _mock_contact()
        mock_db.execute = AsyncMock(return_value=dup_result)

        payload = {
            "phone_number": "+15551234567",
            "country_code": "US",
        }
        resp = await api_client.post(
            "/api/v1/whatsapp/contacts", json=payload, headers=admin_headers
        )
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    # ── Validation: missing required fields → 422 ──────────────────────
    @pytest.mark.asyncio
    async def test_create_contact_validation_error(self, api_client, admin_headers):
        """POST /whatsapp/contacts with missing fields → 422."""
        resp = await api_client.post(
            "/api/v1/whatsapp/contacts",
            json={"display_name": "no phone"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    # ── Bulk import: happy path ────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_bulk_import_contacts(self, api_client, mock_db, admin_headers):
        """POST /whatsapp/contacts/bulk imports multiple contacts."""
        # Each contact does a duplicate check; return None (no dups)
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=dup_result)

        # After flush, the handler reads contact.id; mock db.add so that
        # each object gets a sequential id assigned
        _counter = iter(range(100, 103))

        original_add = mock_db.add

        def _add_with_id(obj):
            obj.id = next(_counter)

        mock_db.add = MagicMock(side_effect=_add_with_id)

        payload = {
            "contacts": [
                {"phone_number": "+15551111111", "country_code": "US"},
                {"phone_number": "+15552222222", "country_code": "US"},
            ]
        }
        resp = await api_client.post(
            "/api/v1/whatsapp/contacts/bulk", json=payload, headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["total"] == 2
        assert body["data"]["success"] == 2
        assert body["data"]["failed"] == 0


class TestWhatsAppTemplates:
    """Tests for WhatsApp template endpoints."""

    @pytest.mark.asyncio
    async def test_list_templates_no_auth(self, api_client):
        """GET /whatsapp/templates without auth → 401/403."""
        resp = await api_client.get("/api/v1/whatsapp/templates")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_list_templates_happy(self, api_client, mock_db, admin_headers):
        """GET /whatsapp/templates returns paginated templates."""
        templates = [_mock_template(id=i) for i in (1, 2)]
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        data_result = make_scalars_result(templates)
        mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

        resp = await api_client.get("/api/v1/whatsapp/templates", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["total"] == 2

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.whatsapp.get_whatsapp_client")
    async def test_create_template_happy(
        self, mock_get_client, api_client, mock_db, admin_headers
    ):
        """POST /whatsapp/templates creates template and submits to Meta."""
        # Mock WhatsApp client
        mock_wa = AsyncMock()
        mock_wa.create_template = AsyncMock(return_value={"id": "meta_tmpl_999"})
        mock_get_client.return_value = mock_wa

        tmpl = _mock_template(id=10, name="promo_launch", status="pending")
        mock_db.refresh = AsyncMock(
            side_effect=lambda obj: [
                setattr(obj, k, getattr(tmpl, k))
                for k in (
                    "id",
                    "name",
                    "language",
                    "category",
                    "body_text",
                    "status",
                    "usage_count",
                    "created_at",
                )
            ]
        )

        payload = {
            "name": "promo_launch",
            "category": "MARKETING",
            "body_text": "Check out our new offer!",
        }
        resp = await api_client.post(
            "/api/v1/whatsapp/templates", json=payload, headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["name"] == "promo_launch"

    @pytest.mark.asyncio
    async def test_create_template_validation_error(self, api_client, admin_headers):
        """POST /whatsapp/templates with missing body_text → 422."""
        payload = {"name": "bad", "category": "MARKETING"}
        resp = await api_client.post(
            "/api/v1/whatsapp/templates", json=payload, headers=admin_headers
        )
        assert resp.status_code == 422


class TestWhatsAppMessages:
    """Tests for WhatsApp message send / broadcast endpoints."""

    @pytest.mark.asyncio
    async def test_send_message_no_auth(self, api_client):
        """POST /whatsapp/messages/send without auth → 401/403."""
        resp = await api_client.post("/api/v1/whatsapp/messages/send", json={})
        assert resp.status_code in (401, 403, 422)

    @pytest.mark.asyncio
    async def test_send_message_happy(self, api_client, mock_db, admin_headers):
        """POST /whatsapp/messages/send queues a message."""
        contact = _mock_contact(opt_in_status="opted_in")
        contact_result = MagicMock()
        contact_result.scalar_one_or_none.return_value = contact
        mock_db.execute = AsyncMock(return_value=contact_result)

        msg = _mock_message(id=42)
        mock_db.refresh = AsyncMock(
            side_effect=lambda obj: [
                setattr(obj, k, getattr(msg, k))
                for k in (
                    "id",
                    "contact_id",
                    "direction",
                    "message_type",
                    "status",
                    "content",
                    "template_name",
                    "sent_at",
                    "delivered_at",
                    "read_at",
                    "created_at",
                )
            ]
        )

        # Mock the celery task that is imported inside the handler
        mock_task = MagicMock()
        mock_task.delay = MagicMock()
        with patch.dict(
            "sys.modules",
            {"app.workers.tasks": MagicMock(send_whatsapp_message=mock_task)},
        ):
            payload = {
                "contact_id": 1,
                "message_type": "text",
                "content": "Hello there!",
            }
            resp = await api_client.post(
                "/api/v1/whatsapp/messages/send", json=payload, headers=admin_headers
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    @pytest.mark.asyncio
    async def test_send_message_contact_not_found(
        self, api_client, mock_db, admin_headers
    ):
        """POST /whatsapp/messages/send with unknown contact → 404."""
        contact_result = MagicMock()
        contact_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=contact_result)

        payload = {
            "contact_id": 999,
            "message_type": "text",
            "content": "Hi",
        }
        resp = await api_client.post(
            "/api/v1/whatsapp/messages/send", json=payload, headers=admin_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_send_message_not_opted_in(self, api_client, mock_db, admin_headers):
        """POST /whatsapp/messages/send to non-opted-in contact → 400."""
        contact = _mock_contact(opt_in_status="pending")
        contact_result = MagicMock()
        contact_result.scalar_one_or_none.return_value = contact
        mock_db.execute = AsyncMock(return_value=contact_result)

        payload = {
            "contact_id": 1,
            "message_type": "text",
            "content": "Hi",
        }
        resp = await api_client.post(
            "/api/v1/whatsapp/messages/send", json=payload, headers=admin_headers
        )
        assert resp.status_code == 400
        assert "opted in" in resp.json()["detail"]


class TestWhatsAppWebhook:
    """Tests for WhatsApp webhook (signature-verified, public)."""

    @pytest.mark.asyncio
    async def test_webhook_missing_signature(self, api_client, admin_headers):
        """POST /whatsapp/webhooks/status without signature header → 401."""
        payload = {"entry": []}
        resp = await api_client.post(
            "/api/v1/whatsapp/webhooks/status",
            json=payload,
            headers=admin_headers,
        )
        assert resp.status_code == 401
        assert "Missing" in resp.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.whatsapp.verify_webhook_signature", return_value=False)
    async def test_webhook_invalid_signature(
        self, mock_verify, api_client, admin_headers
    ):
        """POST /whatsapp/webhooks/status with bad signature → 401."""
        headers = {**admin_headers, "X-Hub-Signature-256": "sha256=invalid"}
        resp = await api_client.post(
            "/api/v1/whatsapp/webhooks/status",
            json={"entry": []},
            headers=headers,
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    @patch("app.api.v1.endpoints.whatsapp.verify_webhook_signature", return_value=True)
    async def test_webhook_valid_signature(
        self, mock_verify, api_client, mock_db, admin_headers
    ):
        """POST /whatsapp/webhooks/status with valid signature → 200."""
        headers = {**admin_headers, "X-Hub-Signature-256": "sha256=valid"}
        payload = {"entry": []}
        resp = await api_client.post(
            "/api/v1/whatsapp/webhooks/status",
            json=payload,
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "received"


# FEATURE 11 - Payments (Stripe) — removed (STRAT-SC-001 / Task A1-A2).
#
# TestPaymentsOverview / TestPaymentsCheckout / TestPaymentsSubscription /
# TestStripeWebhook / TestSubscriptionEndpoints used to exercise
# app.api.v1.endpoints.{payments,stripe_webhook,subscription} and
# app.services.stripe_service. Task A1 unregistered the routers; Task A2
# deleted the endpoint modules, the Stripe service, and the corresponding
# integration test files (test_payments_api.py, test_subscription_api.py,
# test_tier_api.py) outright.

# =============================================================================
# FEATURE 12 - Multi-tenancy
# =============================================================================


class TestTenantsCRUD:
    """Tests for /tenants/* CRUD endpoints."""

    # ── No auth → 401/403 ──────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_list_tenants_no_auth(self, api_client):
        """GET /tenants without auth → 401/403."""
        resp = await api_client.get("/api/v1/tenants")
        assert resp.status_code in (401, 403)

    # ── List tenants: viewer sees only their own ───────────────────────
    @pytest.mark.asyncio
    async def test_list_tenants_viewer_limited(
        self, api_client, mock_db, viewer_headers
    ):
        """GET /tenants as viewer → succeeds but filters to own tenant."""
        tenant = _mock_tenant(id=1)
        data_result = make_scalars_result([tenant])
        mock_db.execute = AsyncMock(return_value=data_result)

        resp = await api_client.get("/api/v1/tenants", headers=viewer_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    # ── List tenants: admin sees all ───────────────────────────────────
    @pytest.mark.asyncio
    async def test_list_tenants_admin(self, api_client, mock_db, admin_headers):
        """GET /tenants as admin → returns all tenants."""
        tenants = [_mock_tenant(id=i, slug=f"tenant-{i}") for i in (1, 2, 3)]
        data_result = make_scalars_result(tenants)
        mock_db.execute = AsyncMock(return_value=data_result)

        resp = await api_client.get("/api/v1/tenants", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 3

    # ── Get current tenant ─────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_get_current_tenant(self, api_client, mock_db, admin_headers):
        """GET /tenants/current returns authenticated user's tenant."""
        tenant = _mock_tenant(id=1)
        tenant_result = make_scalar_result(tenant)
        mock_db.execute = AsyncMock(return_value=tenant_result)

        resp = await api_client.get("/api/v1/tenants/current", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["id"] == 1
        assert body["data"]["slug"] == "acme-inc"

    # ── Get specific tenant: cross-tenant blocked for viewer ───────────
    @pytest.mark.asyncio
    async def test_get_tenant_cross_tenant_blocked(
        self, api_client, mock_db, viewer_headers
    ):
        """GET /tenants/2 as viewer of tenant 1 → 403."""
        resp = await api_client.get("/api/v1/tenants/2", headers=viewer_headers)
        assert resp.status_code == 403

    # ── Get specific tenant: admin can access other tenants ────────────
    @pytest.mark.asyncio
    async def test_get_tenant_owner_cross_tenant(
        self, api_client, mock_db, owner_headers
    ):
        """Cross-tenant read (GET /tenants/2) is allowed for an owner; a
        regular admin is restricted to their own tenant."""
        tenant = _mock_tenant(id=2, slug="other-co")
        tenant_result = make_scalar_result(tenant)
        mock_db.execute = AsyncMock(return_value=tenant_result)

        resp = await api_client.get("/api/v1/tenants/2", headers=owner_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == 2

    # ── Create tenant: viewer blocked ──────────────────────────────────
    @pytest.mark.asyncio
    async def test_create_tenant_viewer_blocked(
        self, api_client, mock_db, viewer_headers
    ):
        """POST /tenants as viewer → 403 (admin required)."""
        payload = {
            "name": "New Co",
            "slug": "new-co",
        }
        resp = await api_client.post(
            "/api/v1/tenants", json=payload, headers=viewer_headers
        )
        assert resp.status_code == 403

    # ── Create tenant: owner happy path ───────────────────────────────
    @pytest.mark.asyncio
    async def test_create_tenant_happy(self, api_client, mock_db, owner_headers):
        """POST /tenants creates a new tenant (owner-only)."""
        # Duplicate check: no existing tenant with slug
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=dup_result)

        new_tenant = _mock_tenant(id=10, name="New Co", slug="new-co", plan="free")
        mock_db.refresh = AsyncMock(
            side_effect=lambda obj: [
                setattr(obj, k, getattr(new_tenant, k))
                for k in (
                    "id",
                    "name",
                    "slug",
                    "domain",
                    "plan",
                    "plan_expires_at",
                    "max_users",
                    "max_campaigns",
                    "settings",
                    "feature_flags",
                    "created_at",
                    "updated_at",
                )
            ]
        )

        payload = {
            "name": "New Co",
            "slug": "new-co",
            "plan": "free",
        }
        resp = await api_client.post(
            "/api/v1/tenants", json=payload, headers=owner_headers
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True

    # ── Create tenant: duplicate slug → 409 ────────────────────────────
    @pytest.mark.asyncio
    async def test_create_tenant_duplicate_slug(
        self, api_client, mock_db, owner_headers
    ):
        """POST /tenants with existing slug → 409 (owner-only)."""
        existing = _mock_tenant(slug="acme-inc")
        dup_result = MagicMock()
        dup_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=dup_result)

        payload = {
            "name": "Another Acme",
            "slug": "acme-inc",
        }
        resp = await api_client.post(
            "/api/v1/tenants", json=payload, headers=owner_headers
        )
        assert resp.status_code == 409

    # ── Validation error ───────────────────────────────────────────────
    @pytest.mark.asyncio
    async def test_create_tenant_validation_error(self, api_client, admin_headers):
        """POST /tenants with invalid slug → 422."""
        payload = {
            "name": "X",
            "slug": "BAD SLUG!",
        }
        resp = await api_client.post(
            "/api/v1/tenants", json=payload, headers=admin_headers
        )
        assert resp.status_code == 422

    # ── Update tenant: viewer blocked ──────────────────────────────────
    @pytest.mark.asyncio
    async def test_update_tenant_viewer_blocked(
        self, api_client, mock_db, viewer_headers
    ):
        """PATCH /tenants/1 as viewer → 403."""
        payload = {"name": "Updated Name"}
        resp = await api_client.patch(
            "/api/v1/tenants/1", json=payload, headers=viewer_headers
        )
        assert resp.status_code == 403

    # ── Update tenant: admin happy ─────────────────────────────────────
    @pytest.mark.asyncio
    async def test_update_tenant_happy(self, api_client, mock_db, admin_headers):
        """PATCH /tenants/1 as admin → updates tenant."""
        tenant = _mock_tenant(id=1)
        tenant_result = make_scalar_result(tenant)
        mock_db.execute = AsyncMock(return_value=tenant_result)

        updated = _mock_tenant(id=1, name="Acme Updated")
        mock_db.refresh = AsyncMock(
            side_effect=lambda obj: [
                setattr(obj, k, getattr(updated, k))
                for k in (
                    "id",
                    "name",
                    "slug",
                    "domain",
                    "plan",
                    "plan_expires_at",
                    "max_users",
                    "max_campaigns",
                    "settings",
                    "feature_flags",
                    "created_at",
                    "updated_at",
                )
            ]
        )

        payload = {"name": "Acme Updated"}
        resp = await api_client.patch(
            "/api/v1/tenants/1", json=payload, headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

    # ── Get tenant users: cross-tenant blocked ─────────────────────────
    @pytest.mark.asyncio
    async def test_get_tenant_users_cross_tenant_blocked(
        self, api_client, mock_db, viewer_headers
    ):
        """GET /tenants/2/users as viewer of tenant 1 → 403."""
        resp = await api_client.get("/api/v1/tenants/2/users", headers=viewer_headers)
        assert resp.status_code == 403

    # ── Get tenant users: happy path ───────────────────────────────────
    @pytest.mark.asyncio
    async def test_get_tenant_users_happy(self, api_client, mock_db, admin_headers):
        """GET /tenants/1/users as admin → returns user count."""
        tenant = _mock_tenant(id=1, max_users=25)
        tenant_result = make_scalar_result(tenant)

        count_result = MagicMock()
        count_result.scalar.return_value = 5

        mock_db.execute = AsyncMock(side_effect=[tenant_result, count_result])

        resp = await api_client.get("/api/v1/tenants/1/users", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["user_count"] == 5
        assert body["data"]["max_users"] == 25
        assert body["data"]["slots_available"] == 20


class TestTenantDashboard:
    """Tests for /tenant/{tenant_id}/dashboard/* and /tenant/{tenant_id}/settings."""

    @pytest.mark.asyncio
    async def test_dashboard_overview_no_auth(self, api_client):
        """GET /tenant/1/dashboard/overview without auth → 401."""
        resp = await api_client.get("/api/v1/tenant/1/dashboard/overview")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_dashboard_overview_cross_tenant_blocked(
        self, api_client, mock_db, tenant2_headers
    ):
        """GET /tenant/1/dashboard/overview as tenant 2 → 403."""
        resp = await api_client.get(
            "/api/v1/tenant/1/dashboard/overview", headers=tenant2_headers
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_dashboard_overview_happy(self, api_client, mock_db, admin_headers):
        """GET /tenant/1/dashboard/overview returns KPIs."""
        # The endpoint fetches campaigns via tenant_query then does math
        empty_result = make_scalars_result([])
        mock_db.execute = AsyncMock(return_value=empty_result)

        resp = await api_client.get(
            "/api/v1/tenant/1/dashboard/overview", headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "total_spend" in body["data"]
        assert "total_campaigns" in body["data"]

    @pytest.mark.asyncio
    async def test_settings_cross_tenant_blocked(
        self, api_client, mock_db, tenant2_headers
    ):
        """GET /tenant/1/settings as tenant 2 → 403."""
        resp = await api_client.get(
            "/api/v1/tenant/1/settings", headers=tenant2_headers
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_settings_happy(self, api_client, mock_db, admin_headers):
        """GET /tenant/1/settings returns tenant settings."""
        tenant = _mock_tenant(id=1)
        tenant_result = make_scalar_result(tenant)
        mock_db.execute = AsyncMock(return_value=tenant_result)

        resp = await api_client.get("/api/v1/tenant/1/settings", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "currency" in body["data"]

    @pytest.mark.asyncio
    async def test_update_settings_cross_tenant_blocked(
        self, api_client, mock_db, tenant2_headers
    ):
        """PUT /tenant/1/settings as tenant 2 → 403."""
        payload = {"currency": "EUR"}
        resp = await api_client.put(
            "/api/v1/tenant/1/settings", json=payload, headers=tenant2_headers
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_update_settings_viewer_reaches_handler(
        self, api_client, mock_db, viewer_headers
    ):
        """PUT /tenant/1/settings as viewer.

        The TENANT_SETTINGS permission gate was removed from this endpoint
        (Permission enum drop, STRAT-SC-001 rename ledger) — tenant_dashboard.py
        is deleted whole in Phase C, so the dependency was dropped rather than
        reworked. A viewer with matching tenant_id now reaches the handler
        (require_tenant still gates cross-tenant access) and gets 404 because
        the mocked DB has no Tenant row, not a 403 permission rejection.
        """
        payload = {"currency": "EUR"}
        resp = await api_client.put(
            "/api/v1/tenant/1/settings", json=payload, headers=viewer_headers
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_settings_admin_happy(
        self, api_client, mock_db, admin_headers
    ):
        """PUT /tenant/1/settings as admin updates settings."""
        tenant = _mock_tenant(id=1)
        tenant_result = make_scalar_result(tenant)
        mock_db.execute = AsyncMock(return_value=tenant_result)
        mock_db.refresh = AsyncMock(
            side_effect=lambda obj: [
                setattr(obj, "settings", {**tenant.settings, "currency": "EUR"}),
                setattr(obj, "feature_flags", tenant.feature_flags),
            ]
        )

        payload = {"currency": "EUR"}
        resp = await api_client.put(
            "/api/v1/tenant/1/settings", json=payload, headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True

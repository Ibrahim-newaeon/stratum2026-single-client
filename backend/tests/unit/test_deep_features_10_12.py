# =============================================================================
# ADs Growth System - Deep Endpoint Tests for Features 10, 11, 12
# =============================================================================
"""
Deep endpoint tests exercising the FULL request/response cycle via
httpx.AsyncClient, going through real middleware (JWT decode)
while mocking services/DB at the endpoint handler level.

Feature 10: WhatsApp Integration
Feature 11: Payments — removed (no billing provider)
Feature 12: Dashboard settings (formerly multi-tenancy; single-org now)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.conftest import make_scalars_result

# =============================================================================
# Helper: mock ORM objects
# =============================================================================


def _mock_contact(**overrides):
    """Build a mock WhatsApp contact ORM object."""
    defaults = dict(
        id=1,
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


# =============================================================================
# FEATURE 10 - WhatsApp Integration
# =============================================================================


class TestWhatsAppContacts:
    """Tests for WhatsApp contact endpoints."""

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


class TestDashboardSettings:
    """Tests for /dashboard/overview and /dashboard/settings (org settings)."""

    @staticmethod
    def _mock_org():
        org = MagicMock()
        org.settings = {"currency": "USD", "timezone": "UTC"}
        org.feature_flags = {"whatsapp": True}
        return org

    @pytest.mark.asyncio
    async def test_dashboard_overview_no_auth(self, api_client):
        """GET /dashboard/overview without auth → 401."""
        resp = await api_client.get("/api/v1/dashboard/overview")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_dashboard_overview_happy(self, api_client, mock_db, admin_headers):
        """GET /dashboard/overview returns KPIs (safe empty with mocked DB)."""
        empty_result = make_scalars_result([])
        mock_db.execute = AsyncMock(return_value=empty_result)

        resp = await api_client.get("/api/v1/dashboard/overview", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "metrics" in body["data"]
        assert "total_campaigns" in body["data"]

    @pytest.mark.asyncio
    async def test_get_settings_no_auth(self, api_client):
        """GET /dashboard/settings without auth → 401."""
        resp = await api_client.get("/api/v1/dashboard/settings")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_settings_happy(self, api_client, mock_db, admin_headers):
        """GET /dashboard/settings returns org settings."""
        mock_db.get = AsyncMock(return_value=self._mock_org())

        resp = await api_client.get("/api/v1/dashboard/settings", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_update_settings_admin_happy(
        self, api_client, mock_db, admin_headers
    ):
        """PUT /dashboard/settings as admin updates org settings."""
        mock_db.get = AsyncMock(return_value=self._mock_org())

        payload = {"currency": "EUR"}
        resp = await api_client.put(
            "/api/v1/dashboard/settings", json=payload, headers=admin_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["currency"] == "EUR"

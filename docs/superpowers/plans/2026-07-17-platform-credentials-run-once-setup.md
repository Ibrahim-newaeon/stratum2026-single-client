# Platform App Credentials + Run-Once Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let each black-box deployment's owner enter ad-platform OAuth app credentials in the UI (DB-first, env fallback), make Connect buttons guide users when credentials are missing, and gate the run-once onboarding wizard to owner/admin roles.

**Architecture:** A new `PlatformAppCredential` table (secrets in transparent `EncryptedString` columns) is read by a resolver (`resolve_app_credentials`: DB row → env settings → typed `CredentialsNotConfigured`). The OAuth service factory loses its singleton cache and accepts resolved credentials; the `/oauth/*` endpoints resolve-then-inject and convert missing credentials into a typed HTTP 400 (`code: credentials_not_configured`). An owner/admin CRUD API + Settings→Integrations panel manage the rows (secrets write-only). The onboarding wizard redirects only owner/admin; backend write endpoints get the same gate.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic + Fernet (`EncryptedString` TypeDecorator), React 18 + TypeScript + @tanstack/react-query, vitest + @testing-library/react, pytest (unit conftest ships AsyncClient with mocked DB + JWT role tokens).

**Spec:** `docs/superpowers/specs/2026-07-17-platform-credentials-and-run-once-setup-design.md`

## Global Constraints

- Backend: type hints required on all functions; models import `Base` from `app.db.base_class`; encrypted columns use `EncryptedString` from `app.db.types` (pattern: `SlackIntegration.webhook_url`, `app/models/settings.py:326`).
- New model MUST be imported in `backend/app/models/__init__.py` (side-effect block ~L175) so Alembic sees it; new router registered in `backend/app/api/v1/__init__.py`.
- Migration chain: new revision's `down_revision = "b7e3f4a9c2d1"`; filename convention `{YYYYMMDD}_{HHMMSS}_{rev}_{slug}.py`.
- Role gate: `from app.auth.deps import require_admin` — it is a factory, use `Depends(require_admin())` (admin + owner).
- Typed error contract (Produces, used by frontend): authorize/callback/refresh endpoints raise `HTTPException(status_code=400, detail={"code": "credentials_not_configured", "message": "<Platform> app credentials are not configured. An owner or admin can add them under Settings → Integrations."})`.
- Secrets NEVER returned by any API after save. `client_id` is not secret (appears in OAuth URLs) and may be returned.
- Frontend: `@/` alias; toasts via `useToast` from `@/components/ui/use-toast`; API via `apiClient`/`ApiResponse` from `@/api/client` (read `response.data.data`); semantic Tailwind tokens only; role from `useAuth().user?.role` (`'owner' | 'admin' | 'manager' | 'analyst' | 'viewer'`).
- Frontend tests colocated `*.test.ts(x)`; run `npx vitest run <path>` from `frontend/`. Backend tests: `python -m pytest tests/unit/<file> -v` from `backend/` (use `python3.12` if `python` missing).
- Conventional commits; every commit message body ends with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- Env var names per platform (fallback source, `app/core/config.py:156-180`): meta → `meta_app_id`/`meta_app_secret`; google → `google_ads_client_id`/`google_ads_client_secret`/`google_ads_developer_token`; tiktok → `tiktok_app_id`/`tiktok_secret` (NOT `tiktok_app_secret`); snapchat → `snapchat_client_id`/`snapchat_client_secret`.

---

### Task 1: `PlatformAppCredential` model + migration

**Files:**
- Create: `backend/app/models/platform_app_credential.py`
- Create: `backend/migrations/versions/20260717_020000_c8d2e5f7a1b3_add_platform_app_credential.py`
- Modify: `backend/app/models/__init__.py` (side-effect import block ~L175 and `__all__` re-export)
- Test: `backend/tests/unit/test_platform_app_credential_model.py`

**Interfaces:**
- Produces: `PlatformAppCredential` with columns `id`, `platform` (String(20), unique, not null), `client_id` (String(255), not null), `client_secret` (EncryptedString(1024), not null), `developer_token` (EncryptedString(1024), nullable), `updated_by_user_id` (Integer, nullable), `created_at`/`updated_at` (TimestampMixin). Exported from `app.models`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_platform_app_credential_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python -m pytest tests/unit/test_platform_app_credential_model.py -v`
Expected: FAIL — `ModuleNotFoundError: app.models.platform_app_credential`.
NOTE: if `EncryptedString.process_bind_param`/`process_result_value` signatures differ (read `app/db/types.py` first), adapt the round-trip test to the real TypeDecorator API — the assertion semantics (stored ≠ plaintext, decrypt returns plaintext) stay.

- [ ] **Step 3: Write the model**

```python
# backend/app/models/platform_app_credential.py
# =============================================================================
# ADs Growth System - Platform App Credentials
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
    platform: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret: Mapped[str] = mapped_column(EncryptedString(1024), nullable=False)
    developer_token: Mapped[str | None] = mapped_column(
        EncryptedString(1024), nullable=True
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

NOTE: read `app/db/base_class.py` first — if `TimestampMixin` lives elsewhere or `Base` already provides timestamps, match the convention used by `app/models/settings.py` (SlackIntegration) exactly.

- [ ] **Step 4: Register the model**

In `backend/app/models/__init__.py`: add `platform_app_credential,` to the side-effect import tuple (~L175, alphabetical position) AND add a re-export:

```python
from app.models.platform_app_credential import PlatformAppCredential
```

plus `"PlatformAppCredential",` in `__all__`.

- [ ] **Step 5: Write the migration**

```python
# backend/migrations/versions/20260717_020000_c8d2e5f7a1b3_add_platform_app_credential.py
"""Add platform_app_credential table (per-deployment OAuth app credentials).

Revision ID: c8d2e5f7a1b3
Revises: b7e3f4a9c2d1
Create Date: 2026-07-17 02:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

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
        # EncryptedString maps to a sized String/Text at the DB layer; the
        # encryption happens in the type decorator, so plain String here.
        sa.Column("client_secret", sa.String(length=1024), nullable=False),
        sa.Column("developer_token", sa.String(length=1024), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_platform_app_credential_platform",
        "platform_app_credential",
        ["platform"],
    )
    op.create_unique_constraint(
        "uq_platform_app_credential_platform",
        "platform_app_credential",
        ["platform"],
    )


def downgrade() -> None:
    op.drop_table("platform_app_credential")
```

NOTE: check how the initial migration (`20260714_152542_12a656044fcc_...py`) declares timestamp columns for tables using `TimestampMixin` and mirror it exactly (nullable/server_default conventions).

- [ ] **Step 6: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_platform_app_credential_model.py -v`
Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/platform_app_credential.py backend/app/models/__init__.py backend/migrations/versions/20260717_020000_c8d2e5f7a1b3_add_platform_app_credential.py backend/tests/unit/test_platform_app_credential_model.py
git commit -m "feat(credentials): PlatformAppCredential model + migration (encrypted at rest)"
```

---

### Task 2: Credentials resolver (DB-first, env fallback)

**Files:**
- Create: `backend/app/services/oauth/credentials.py`
- Test: `backend/tests/unit/test_oauth_credentials_resolver.py`

**Interfaces:**
- Produces (consumed by Tasks 3, 4, 5):

```python
@dataclass(frozen=True)
class AppCredentials:
    platform: str
    client_id: str
    client_secret: str
    developer_token: str | None
    source: str  # "database" | "environment"

class CredentialsNotConfigured(Exception):
    def __init__(self, platform: str) -> None: ...
    # .platform attribute; str(exc) is the user-facing message below

async def resolve_app_credentials(platform: str, db: AsyncSession) -> AppCredentials

ENV_CREDENTIAL_FIELDS: dict[str, tuple[str, str, str | None]]
# platform -> (settings attr for client_id, for client_secret, for developer_token or None)

def credentials_message(platform: str) -> str
# "<Platform label> app credentials are not configured. An owner or admin can add them under Settings → Integrations."

PLATFORM_LABELS = {"meta": "Meta", "google": "Google Ads", "tiktok": "TikTok", "snapchat": "Snapchat"}
```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_oauth_credentials_resolver.py
"""resolve_app_credentials: DB row wins, env falls back, else typed error."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.oauth.credentials import (
    AppCredentials,
    CredentialsNotConfigured,
    credentials_message,
    resolve_app_credentials,
)


def _db_returning(row: object | None) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db.execute.return_value = result
    return db


@pytest.mark.asyncio
async def test_db_row_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "meta_app_id", "env-id")
    monkeypatch.setattr(settings, "meta_app_secret", "env-secret")
    row = MagicMock(
        platform="meta",
        client_id="db-id",
        client_secret="db-secret",
        developer_token=None,
    )
    creds = await resolve_app_credentials("meta", _db_returning(row))
    assert creds == AppCredentials(
        platform="meta",
        client_id="db-id",
        client_secret="db-secret",
        developer_token=None,
        source="database",
    )


@pytest.mark.asyncio
async def test_env_fallback_when_no_db_row(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_ads_client_id", "g-id")
    monkeypatch.setattr(settings, "google_ads_client_secret", "g-secret")
    monkeypatch.setattr(settings, "google_ads_developer_token", "g-dev")
    creds = await resolve_app_credentials("google", _db_returning(None))
    assert creds.source == "environment"
    assert creds.client_id == "g-id"
    assert creds.developer_token == "g-dev"


@pytest.mark.asyncio
async def test_raises_typed_error_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "tiktok_app_id", None)
    monkeypatch.setattr(settings, "tiktok_secret", None)
    with pytest.raises(CredentialsNotConfigured) as exc:
        await resolve_app_credentials("tiktok", _db_returning(None))
    assert exc.value.platform == "tiktok"


def test_message_names_the_platform_and_the_fix() -> None:
    msg = credentials_message("meta")
    assert "Meta app credentials are not configured" in msg
    assert "Settings → Integrations" in msg


@pytest.mark.asyncio
async def test_unknown_platform_raises() -> None:
    with pytest.raises(CredentialsNotConfigured):
        await resolve_app_credentials("myspace", _db_returning(None))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_oauth_credentials_resolver.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/oauth/credentials.py
# =============================================================================
# ADs Growth System - OAuth App Credential Resolution
# =============================================================================
"""
Resolve per-platform OAuth *application* credentials.

Order: PlatformAppCredential DB row (owner-managed, black-box deployments)
→ env settings fallback (vendor-managed) → CredentialsNotConfigured.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.platform_app_credential import PlatformAppCredential

PLATFORM_LABELS: dict[str, str] = {
    "meta": "Meta",
    "google": "Google Ads",
    "tiktok": "TikTok",
    "snapchat": "Snapchat",
}

# platform -> (settings attr: client_id, client_secret, developer_token|None)
ENV_CREDENTIAL_FIELDS: dict[str, tuple[str, str, Optional[str]]] = {
    "meta": ("meta_app_id", "meta_app_secret", None),
    "google": (
        "google_ads_client_id",
        "google_ads_client_secret",
        "google_ads_developer_token",
    ),
    "tiktok": ("tiktok_app_id", "tiktok_secret", None),
    "snapchat": ("snapchat_client_id", "snapchat_client_secret", None),
}


def credentials_message(platform: str) -> str:
    label = PLATFORM_LABELS.get(platform, platform)
    return (
        f"{label} app credentials are not configured. "
        "An owner or admin can add them under Settings → Integrations."
    )


class CredentialsNotConfigured(Exception):
    """No DB row and no env vars for this platform's OAuth app."""

    def __init__(self, platform: str) -> None:
        self.platform = platform
        super().__init__(credentials_message(platform))


@dataclass(frozen=True)
class AppCredentials:
    platform: str
    client_id: str
    client_secret: str
    developer_token: Optional[str]
    source: str  # "database" | "environment"


async def resolve_app_credentials(platform: str, db: AsyncSession) -> AppCredentials:
    """DB-first, env-fallback resolution of a platform's app credentials."""
    platform = platform.lower()
    if platform not in ENV_CREDENTIAL_FIELDS:
        raise CredentialsNotConfigured(platform)

    result = await db.execute(
        select(PlatformAppCredential).where(
            PlatformAppCredential.platform == platform
        )
    )
    row = result.scalar_one_or_none()
    if row is not None and row.client_id and row.client_secret:
        return AppCredentials(
            platform=platform,
            client_id=row.client_id,
            client_secret=row.client_secret,
            developer_token=row.developer_token,
            source="database",
        )

    id_attr, secret_attr, dev_attr = ENV_CREDENTIAL_FIELDS[platform]
    client_id = getattr(settings, id_attr, None)
    client_secret = getattr(settings, secret_attr, None)
    if client_id and client_secret:
        return AppCredentials(
            platform=platform,
            client_id=client_id,
            client_secret=client_secret,
            developer_token=getattr(settings, dev_attr, None) if dev_attr else None,
            source="environment",
        )

    raise CredentialsNotConfigured(platform)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/unit/test_oauth_credentials_resolver.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/oauth/credentials.py backend/tests/unit/test_oauth_credentials_resolver.py
git commit -m "feat(credentials): DB-first resolver with env fallback and typed error"
```

---

### Task 3: OAuth services accept resolved credentials; endpoints inject them; typed 400

**Files:**
- Modify: `backend/app/services/oauth/factory.py` (drop singleton cache; accept credentials)
- Modify: `backend/app/services/oauth/base.py` (add `apply_credentials`)
- Modify: `backend/app/services/oauth/meta.py`, `google.py`, `tiktok.py`, `snapchat.py` (override `apply_credentials`)
- Modify: `backend/app/api/v1/endpoints/oauth.py` (resolve + inject at ALL `get_oauth_service` call sites: L182, L275, L557, L692, L834, L922; typed 400)
- Test: `backend/tests/unit/test_oauth_credentials_injection.py`

**Interfaces:**
- Consumes: `AppCredentials`, `resolve_app_credentials`, `CredentialsNotConfigured`, `credentials_message` (Task 2).
- Produces: `get_oauth_service(platform: str, credentials: AppCredentials | None = None) -> OAuthService` (fresh instance per call); `OAuthService.apply_credentials(credentials: AppCredentials) -> None`; oauth endpoints raise the Global-Constraints typed 400 when unconfigured.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_oauth_credentials_injection.py
"""Factory injects resolved credentials; authorize returns typed 400."""

import pytest

from app.services.oauth.credentials import AppCredentials
from app.services.oauth.factory import get_oauth_service


def _creds(platform: str) -> AppCredentials:
    return AppCredentials(
        platform=platform,
        client_id="cid-123",
        client_secret="sec-456",
        developer_token="dev-789" if platform == "google" else None,
        source="database",
    )


def test_factory_returns_fresh_instances() -> None:
    a = get_oauth_service("meta")
    b = get_oauth_service("meta")
    assert a is not b  # singleton cache removed — per-request credentials


def test_meta_apply_credentials_sets_app_fields() -> None:
    svc = get_oauth_service("meta", credentials=_creds("meta"))
    assert svc.app_id == "cid-123"
    assert svc.app_secret == "sec-456"


@pytest.mark.parametrize("platform", ["google", "tiktok", "snapchat"])
def test_all_services_accept_credentials(platform: str) -> None:
    svc = get_oauth_service(platform, credentials=_creds(platform))
    # Every service must expose the injected values through whatever
    # attribute names it uses internally; verify via authorization URL
    # construction not raising the "not configured" ValueError.
    # (Attribute names differ per service; the URL builder is the contract.)
    from app.services.oauth.base import OAuthState

    state = OAuthState(state="s" * 32, platform=platform, user_id=1)
    url = svc.get_authorization_url(state)
    assert "cid-123" in url
```

NOTE: read `base.py`'s `OAuthState` definition first (L~90-119) and construct it with its REAL required fields; the intent is a syntactically valid state object. If `get_authorization_url` needs more context for some platform, assert instead on the service's credential attributes after reading each service's `__init__` to learn their names (expected: google → `client_id`/`client_secret`/`developer_token`; tiktok → `app_id`/`secret`; snapchat → `client_id`/`client_secret` — verify against the files).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_oauth_credentials_injection.py -v`
Expected: FAIL — `get_oauth_service() got an unexpected keyword argument 'credentials'` (and singleton test fails: same instance).

- [ ] **Step 3: Implement**

3a. `base.py` — add to `OAuthService` (near `__init__`):

```python
def apply_credentials(self, credentials: "AppCredentials") -> None:
    """Inject resolved app credentials (DB-first/env). Subclasses map the
    generic fields onto their own attribute names."""
    raise NotImplementedError
```

with `from app.services.oauth.credentials import AppCredentials` under `TYPE_CHECKING` (avoid an import cycle: credentials.py imports models only, so a plain import is also fine — prefer plain import if no cycle).

3b. Each service overrides it, assigning to the SAME attributes its `__init__` sets from settings (read each file; expected mapping):

```python
# meta.py
def apply_credentials(self, credentials: AppCredentials) -> None:
    self.app_id = credentials.client_id
    self.app_secret = credentials.client_secret

# google.py
def apply_credentials(self, credentials: AppCredentials) -> None:
    self.client_id = credentials.client_id
    self.client_secret = credentials.client_secret
    if credentials.developer_token:
        self.developer_token = credentials.developer_token

# tiktok.py
def apply_credentials(self, credentials: AppCredentials) -> None:
    self.app_id = credentials.client_id
    self.secret = credentials.client_secret

# snapchat.py
def apply_credentials(self, credentials: AppCredentials) -> None:
    self.client_id = credentials.client_id
    self.client_secret = credentials.client_secret
```

Adjust attribute names to whatever each `__init__` actually assigns (verify; note them in your report if they differ from the above).

3c. `factory.py` — remove the `_oauth_instances` cache entirely; new signature:

```python
def get_oauth_service(
    platform: str, credentials: Optional[AppCredentials] = None
) -> OAuthService:
    platform_lower = platform.lower()
    service_class = _OAUTH_SERVICES.get(platform_lower)
    if service_class is None:
        raise ValueError(f"Unsupported OAuth platform: {platform}")
    service = service_class()
    if credentials is not None:
        service.apply_credentials(credentials)
    return service
```

(Keep `_OAUTH_SERVICES` registry as-is; delete the cache dict and any cache-reset helper, updating whatever referenced it.)

3d. `oauth.py` — add a resolve-and-build helper near the top (after imports):

```python
from app.services.oauth.credentials import (
    CredentialsNotConfigured,
    credentials_message,
    resolve_app_credentials,
)


async def _resolved_oauth_service(platform: str, db: AsyncSession) -> OAuthService:
    """get_oauth_service with DB-first credentials; typed 400 when missing."""
    try:
        credentials = await resolve_app_credentials(platform, db)
    except CredentialsNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "credentials_not_configured",
                "message": credentials_message(exc.platform),
            },
        ) from exc
    return get_oauth_service(platform, credentials=credentials)
```

Replace every `oauth_service = get_oauth_service(platform.value)` call site (L182, L275, L557, L692, L834, L922 — grep for `get_oauth_service(` to be exhaustive) with `oauth_service = await _resolved_oauth_service(platform.value, db)`. Each site already has a `db: AsyncSession` in scope (verify per site; the callback at L275 does — check and report if any site lacks one, and thread the session there).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/test_oauth_credentials_injection.py tests/unit/test_oauth_credentials_resolver.py -v`
Expected: all PASS. Also run any existing oauth unit tests: `python -m pytest tests/unit -k oauth -v` — no regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/oauth backend/app/api/v1/endpoints/oauth.py backend/tests/unit/test_oauth_credentials_injection.py
git commit -m "feat(oauth): per-request credential injection, typed 400 when unconfigured"
```

---

### Task 4: Credentials CRUD API

**Files:**
- Create: `backend/app/api/v1/endpoints/platform_credentials.py`
- Modify: `backend/app/api/v1/__init__.py` (import + `include_router`)
- Test: `backend/tests/unit/test_platform_credentials_api.py`

**Interfaces:**
- Consumes: `PlatformAppCredential` (Task 1), `ENV_CREDENTIAL_FIELDS`/`PLATFORM_LABELS` (Task 2), `require_admin` from `app.auth.deps`, `AuditLog`/`AuditAction` from `app.models` (members: CREATE/UPDATE/DELETE), `APIResponse` + session dep exactly as `oauth.py` uses them.
- Produces (consumed by frontend Task 7):
  - `GET /platform-credentials` → `data: [{ platform, configured: bool, source: "database"|"environment"|null, client_id: str|null, has_developer_token: bool, callback_url: str }]` (all four platforms, always).
  - `PUT /platform-credentials/{platform}` body `{ client_id: str, client_secret?: str, developer_token?: str }` — secret required when creating; omitted/empty secret on update keeps the stored one. 422 on unknown platform.
  - `DELETE /platform-credentials/{platform}` → removes DB row (env fallback resumes if present).
  - All routes `dependencies=[Depends(require_admin())]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_platform_credentials_api.py
"""Platform credentials CRUD: role gate, secret masking, keep-secret update."""

from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
async def test_list_requires_admin(client, viewer_token) -> None:
    resp = await client.get(
        "/api/v1/platform-credentials",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_returns_all_platforms_and_never_secrets(
    client, admin_token, mock_db
) -> None:
    row = MagicMock(
        platform="meta",
        client_id="cid-1",
        client_secret="SHOULD-NEVER-APPEAR",
        developer_token=None,
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [row]
    mock_db.execute.return_value = result

    resp = await client.get(
        "/api/v1/platform-credentials",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    platforms = {item["platform"] for item in body["data"]}
    assert platforms == {"meta", "google", "tiktok", "snapchat"}
    assert "SHOULD-NEVER-APPEAR" not in resp.text
    meta = next(i for i in body["data"] if i["platform"] == "meta")
    assert meta["configured"] is True
    assert meta["source"] == "database"
    assert meta["client_id"] == "cid-1"
    assert "/api/v1/oauth/meta/callback" in meta["callback_url"]


@pytest.mark.asyncio
async def test_put_unknown_platform_is_422(client, admin_token) -> None:
    resp = await client.put(
        "/api/v1/platform-credentials/myspace",
        json={"client_id": "x", "client_secret": "y"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_create_requires_secret(client, admin_token, mock_db) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # no existing row
    mock_db.execute.return_value = result
    resp = await client.put(
        "/api/v1/platform-credentials/meta",
        json={"client_id": "cid-1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
```

NOTE: fixture names (`client`, `admin_token`, `viewer_token`, `mock_db`) come from `backend/tests/unit/conftest.py` (L~150-250: AsyncClient with `dependency_overrides` on the session and a JWT-derived synthetic user; `_make_token` role fixtures). Read the conftest and use its EXACT fixture names — adjust if they differ (e.g. the client fixture may be named `client` or `async_client`).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_platform_credentials_api.py -v`
Expected: FAIL — 404s (router not registered / module missing).

- [ ] **Step 3: Write the endpoint module**

```python
# backend/app/api/v1/endpoints/platform_credentials.py
# =============================================================================
# ADs Growth System - Platform App Credentials CRUD (owner/admin)
# =============================================================================
"""
Owner/admin management of per-deployment OAuth app credentials.

Secrets are write-only: accepted in PUT bodies, stored encrypted
(EncryptedString), and never serialized back in any response.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import VerifiedUserDep, require_admin
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_async_session
from app.models import AuditAction, AuditLog
from app.models.platform_app_credential import PlatformAppCredential
from app.schemas.common import APIResponse
from app.services.oauth.credentials import ENV_CREDENTIAL_FIELDS, PLATFORM_LABELS

logger = get_logger(__name__)

router = APIRouter(
    prefix="/platform-credentials",
    dependencies=[Depends(require_admin())],
)

_VALID_PLATFORMS = set(ENV_CREDENTIAL_FIELDS.keys())


def _callback_url(platform: str) -> str:
    base_url = settings.oauth_redirect_base_url.rstrip("/")
    return f"{base_url}/api/v1/oauth/{platform}/callback"


class CredentialUpsertRequest(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=255)
    client_secret: Optional[str] = Field(default=None, max_length=1024)
    developer_token: Optional[str] = Field(default=None, max_length=1024)

    @field_validator("client_id")
    @classmethod
    def strip_client_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("client_id must not be blank")
        return v


class CredentialStatus(BaseModel):
    platform: str
    configured: bool
    source: Optional[str]  # "database" | "environment" | None
    client_id: Optional[str]
    has_developer_token: bool
    callback_url: str


def _validate_platform(platform: str) -> str:
    platform = platform.lower()
    if platform not in _VALID_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown platform: {platform}",
        )
    return platform


@router.get("", response_model=APIResponse[list[CredentialStatus]])
async def list_credentials(
    current_user: VerifiedUserDep,
    db: AsyncSession = Depends(get_async_session),
):
    result = await db.execute(select(PlatformAppCredential))
    rows = {r.platform: r for r in result.scalars().all()}

    statuses: list[CredentialStatus] = []
    for platform in sorted(_VALID_PLATFORMS):
        row = rows.get(platform)
        if row is not None:
            statuses.append(
                CredentialStatus(
                    platform=platform,
                    configured=True,
                    source="database",
                    client_id=row.client_id,
                    has_developer_token=bool(row.developer_token),
                    callback_url=_callback_url(platform),
                )
            )
            continue
        id_attr, secret_attr, dev_attr = ENV_CREDENTIAL_FIELDS[platform]
        env_id = getattr(settings, id_attr, None)
        env_secret = getattr(settings, secret_attr, None)
        env_configured = bool(env_id and env_secret)
        statuses.append(
            CredentialStatus(
                platform=platform,
                configured=env_configured,
                source="environment" if env_configured else None,
                client_id=env_id if env_configured else None,
                has_developer_token=bool(
                    dev_attr and getattr(settings, dev_attr, None)
                ),
                callback_url=_callback_url(platform),
            )
        )
    return APIResponse(success=True, data=statuses)


@router.put("/{platform}", response_model=APIResponse[CredentialStatus])
async def upsert_credentials(
    platform: str,
    data: CredentialUpsertRequest,
    request: Request,
    current_user: VerifiedUserDep,
    db: AsyncSession = Depends(get_async_session),
):
    platform = _validate_platform(platform)
    result = await db.execute(
        select(PlatformAppCredential).where(
            PlatformAppCredential.platform == platform
        )
    )
    row = result.scalar_one_or_none()

    secret = (data.client_secret or "").strip()
    if row is None and not secret:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="client_secret is required when adding credentials",
        )

    if row is None:
        row = PlatformAppCredential(
            platform=platform,
            client_id=data.client_id,
            client_secret=secret,
            developer_token=(data.developer_token or "").strip() or None,
            updated_by_user_id=current_user.user.id,
        )
        db.add(row)
        action = AuditAction.CREATE
    else:
        row.client_id = data.client_id
        if secret:
            row.client_secret = secret
        if data.developer_token is not None:
            row.developer_token = data.developer_token.strip() or None
        row.updated_by_user_id = current_user.user.id
        action = AuditAction.UPDATE

    db.add(
        AuditLog(
            user_id=current_user.user.id,
            action=action,
            resource_type="platform_app_credential",
            resource_id=platform,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent", "")[:500],
        )
    )
    await db.commit()
    logger.info(
        "platform_app_credentials_saved",
        platform=platform,
        source="database",
        user_id=current_user.user.id,
    )
    return APIResponse(
        success=True,
        data=CredentialStatus(
            platform=platform,
            configured=True,
            source="database",
            client_id=data.client_id,
            has_developer_token=bool(
                (data.developer_token or "").strip()
                or (row.developer_token if row else None)
            ),
            callback_url=_callback_url(platform),
        ),
        message=f"{PLATFORM_LABELS[platform]} credentials saved",
    )


@router.delete("/{platform}", response_model=APIResponse[dict])
async def delete_credentials(
    platform: str,
    request: Request,
    current_user: VerifiedUserDep,
    db: AsyncSession = Depends(get_async_session),
):
    platform = _validate_platform(platform)
    result = await db.execute(
        select(PlatformAppCredential).where(
            PlatformAppCredential.platform == platform
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored credentials for {platform}",
        )
    await db.delete(row)
    db.add(
        AuditLog(
            user_id=current_user.user.id,
            action=AuditAction.DELETE,
            resource_type="platform_app_credential",
            resource_id=platform,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent", "")[:500],
        )
    )
    await db.commit()
    logger.info(
        "platform_app_credentials_deleted",
        platform=platform,
        user_id=current_user.user.id,
    )
    return APIResponse(success=True, data={"platform": platform, "deleted": True})
```

NOTE: verify the exact import paths used by `oauth.py` for `APIResponse` (`app.schemas.common`?), `get_async_session`, and `VerifiedUserDep`, and mirror them (open `oauth.py` L1-70 and copy its imports). If `APIResponse` is generic-subscripted differently, match `oauth.py`.

- [ ] **Step 4: Register the router**

In `backend/app/api/v1/__init__.py`: add `platform_credentials` to the endpoints import tuple (alphabetical), and next to the oauth registration (~L358):

```python
api_router.include_router(
    platform_credentials.router,
    tags=["Platform Credentials"],
)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/unit/test_platform_credentials_api.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/endpoints/platform_credentials.py backend/app/api/v1/__init__.py backend/tests/unit/test_platform_credentials_api.py
git commit -m "feat(credentials): owner/admin CRUD API with write-only secrets + audit"
```

---

### Task 5: Console credentials health shows source; onboarding write endpoints admin-gated

**Files:**
- Modify: `backend/app/api/v1/endpoints/console.py` (`credentials_health`, ad_platforms section L808-834)
- Modify: `backend/app/api/v1/endpoints/onboarding.py` (write endpoints get admin gate)
- Test: `backend/tests/unit/test_onboarding_role_gate.py`

**Interfaces:**
- Consumes: `PlatformAppCredential` (Task 1), `require_admin` factory.
- Produces: each ad_platform entry in `/console/credentials/health` gains `"source": "database" | "environment" | null`; onboarding write endpoints return 403 for roles below admin.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_onboarding_role_gate.py
"""Onboarding writes are owner/admin-only; reads stay open (guard uses them)."""

import pytest


@pytest.mark.asyncio
async def test_viewer_cannot_write_onboarding(client, viewer_token) -> None:
    resp = await client.post(
        "/api/v1/onboarding/skip",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_can_read_onboarding_check(client, viewer_token, mock_db) -> None:
    resp = await client.get(
        "/api/v1/onboarding/check",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 200
```

(Adjust the mock_db behavior for `/check` if it queries — mirror how existing onboarding unit tests, if any, stub the session; a `scalar_one_or_none → None` default MagicMock usually suffices.)

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/unit/test_onboarding_role_gate.py -v`
Expected: `test_viewer_cannot_write_onboarding` FAILS (currently 200/400, not 403).

- [ ] **Step 3: Gate the write endpoints**

In `onboarding.py`, add near the top: `from app.auth.deps import require_admin` and `_admin_deps = [Depends(require_admin())]`. Add `dependencies=_admin_deps` to the decorators of exactly these routes: `/business-profile` (L410), `/platform-selection` (L455), `/goals-setup` (L495), `/automation-preferences` (L544), `/trust-gate-config` (L599), `/skip` (L656), `/reset` (L696). Leave `/status` and `/check` untouched.

- [ ] **Step 4: Extend console health with source**

In `console.py` `credentials_health`: add a DB query before building the dict (the endpoint must gain `db: AsyncSession = Depends(get_async_session)` if it doesn't have one — mirror the dependency style used elsewhere in the file):

```python
from app.models.platform_app_credential import PlatformAppCredential

result = await db.execute(select(PlatformAppCredential))
db_creds = {r.platform: r for r in result.scalars().all()}

def _source(platform: str, env_configured: bool) -> str | None:
    if platform in db_creds:
        return "database"
    return "environment" if env_configured else None
```

and add to each of the four platform dicts a `"source"` entry, e.g. for meta:

```python
"meta": {
    "app_id": present(settings.meta_app_id) or "meta" in db_creds,
    "app_secret": present(settings.meta_app_secret) or "meta" in db_creds,
    "api_version": settings.meta_api_version or None,
    "long_lived_token": present(settings.meta_access_token),
    "source": _source("meta", present(settings.meta_app_id) and present(settings.meta_app_secret)),
},
```

(equivalent for google_ads with key "google" in db_creds, tiktok, snapchat).

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/unit/test_onboarding_role_gate.py -v` → 2 PASS.
Run: `python -m pytest tests/unit -k "console or onboarding" -v` → no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/endpoints/onboarding.py backend/app/api/v1/endpoints/console.py backend/tests/unit/test_onboarding_role_gate.py
git commit -m "feat(setup): admin-gate onboarding writes; console health reports credential source"
```

---

### Task 6: Frontend — error helper handles object detail; `useAppCredentials` API module

**Files:**
- Modify: `frontend/src/api/client.ts` (`getApiErrorMessage` — object-detail support; new `getApiErrorCode`)
- Create: `frontend/src/api/appCredentials.ts`
- Test: `frontend/src/api/appCredentials.test.tsx`; extend `frontend/src/api/getApiErrorMessage.test.ts`

**Interfaces:**
- Consumes: Task 4's API shapes.
- Produces (consumed by Tasks 7–8):
  - `getApiErrorMessage(error, fallback?)` now also reads `detail.message` when `detail` is an object.
  - `getApiErrorCode(error): string | null` — reads `error.response.data.detail.code` (object detail) else `error.response.data.code`, else null.
  - `CREDENTIALS_NOT_CONFIGURED = 'credentials_not_configured'` exported from `@/api/appCredentials`.
  - `interface AppCredentialStatus { platform: AdPlatform; configured: boolean; source: 'database' | 'environment' | null; client_id: string | null; has_developer_token: boolean; callback_url: string }`
  - `useAppCredentials()` → `{ credentials: AppCredentialStatus[], isLoading, isError, ... }` (queryKey `['app-credentials']`)
  - `useSaveAppCredentials()` mutation (`PUT /platform-credentials/{platform}`, body `{ client_id, client_secret?, developer_token? }`), invalidates `['app-credentials']` and `['connections']`
  - `useDeleteAppCredentials()` mutation (DELETE), same invalidations.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/api/getApiErrorMessage.test.ts`:

```tsx
import { getApiErrorCode } from './client';

describe('object-shaped detail (typed backend errors)', () => {
  it('reads detail.message and detail.code', () => {
    const err = axiosErrorWith(
      { detail: { code: 'credentials_not_configured', message: 'Meta app credentials are not configured.' } },
      400
    );
    expect(getApiErrorMessage(err)).toBe('Meta app credentials are not configured.');
    expect(getApiErrorCode(err)).toBe('credentials_not_configured');
  });

  it('getApiErrorCode returns null when absent', () => {
    expect(getApiErrorCode(axiosErrorWith({ detail: 'plain' }))).toBeNull();
    expect(getApiErrorCode(new Error('x'))).toBeNull();
  });
});
```

Create `frontend/src/api/appCredentials.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

vi.mock('@/api/client', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, apiClient: { get: vi.fn(), put: vi.fn(), delete: vi.fn() } };
});

import { apiClient } from '@/api/client';
import { useAppCredentials, useSaveAppCredentials } from './appCredentials';

const mockedGet = vi.mocked(apiClient.get);
const mockedPut = vi.mocked(apiClient.put);

let qc: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
});

describe('useAppCredentials', () => {
  it('fetches the credential status list', async () => {
    mockedGet.mockResolvedValueOnce({
      data: {
        data: [
          {
            platform: 'meta', configured: true, source: 'database',
            client_id: 'cid', has_developer_token: false,
            callback_url: 'https://api.example/api/v1/oauth/meta/callback',
          },
        ],
      },
    } as never);
    const { result } = renderHook(() => useAppCredentials(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(mockedGet).toHaveBeenCalledWith('/platform-credentials');
    expect(result.current.credentials[0].source).toBe('database');
  });
});

describe('useSaveAppCredentials', () => {
  it('PUTs to the platform path and invalidates queries', async () => {
    mockedPut.mockResolvedValueOnce({ data: { data: {} } } as never);
    const invalidate = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useSaveAppCredentials(), { wrapper });
    await result.current.mutateAsync({
      platform: 'meta',
      client_id: 'cid',
      client_secret: 'sec',
    });
    expect(mockedPut).toHaveBeenCalledWith('/platform-credentials/meta', {
      client_id: 'cid',
      client_secret: 'sec',
      developer_token: undefined,
    });
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ['app-credentials'] })
    );
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['connections'] });
  });
});
```

- [ ] **Step 2: Run to verify RED**

Run: `npx vitest run src/api/appCredentials.test.tsx src/api/getApiErrorMessage.test.ts`
Expected: FAIL — missing module / missing `getApiErrorCode` export.

- [ ] **Step 3: Implement**

3a. In `client.ts`, extend `getApiErrorMessage` (insert before the string-detail checks' fallthrough) and add `getApiErrorCode`:

```ts
export function getApiErrorMessage(
  error: unknown,
  fallback = 'Something went wrong. Please try again.'
): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: unknown; message?: unknown }
      | undefined;
    const detail = data?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (detail && typeof detail === 'object') {
      const msg = (detail as { message?: unknown }).message;
      if (typeof msg === 'string' && msg) return msg;
    }
    if (typeof data?.message === 'string' && data.message) return data.message;
    return error.message || fallback;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/** Machine-readable error code from typed backend errors (detail.code). */
export function getApiErrorCode(error: unknown): string | null {
  if (!axios.isAxiosError(error)) return null;
  const data = error.response?.data as
    | { detail?: unknown; code?: unknown }
    | undefined;
  const detail = data?.detail;
  if (detail && typeof detail === 'object') {
    const code = (detail as { code?: unknown }).code;
    if (typeof code === 'string') return code;
  }
  if (typeof data?.code === 'string') return data.code;
  return null;
}
```

3b. `frontend/src/api/appCredentials.ts`:

```ts
/**
 * ADs Growth System - Platform app credentials (owner/admin).
 *
 * Per-deployment OAuth application credentials, managed in the UI for the
 * black-box model. Secrets are write-only: sent on save, never read back.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient, ApiResponse } from './client';
import type { AdPlatform } from './connections';

export const CREDENTIALS_NOT_CONFIGURED = 'credentials_not_configured';

export interface AppCredentialStatus {
  platform: AdPlatform;
  configured: boolean;
  source: 'database' | 'environment' | null;
  client_id: string | null;
  has_developer_token: boolean;
  callback_url: string;
}

export interface SaveCredentialsInput {
  platform: AdPlatform;
  client_id: string;
  client_secret?: string;
  developer_token?: string;
}

export function useAppCredentials(enabled = true) {
  const query = useQuery({
    queryKey: ['app-credentials'],
    queryFn: async (): Promise<AppCredentialStatus[]> => {
      const res =
        await apiClient.get<ApiResponse<AppCredentialStatus[]>>(
          '/platform-credentials'
        );
      return res.data.data ?? [];
    },
    enabled,
    retry: false, // 403 for non-admins — do not hammer
    staleTime: 60 * 1000,
  });
  return { ...query, credentials: query.data ?? [] };
}

function useInvalidateCredentialQueries() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ['app-credentials'] });
    queryClient.invalidateQueries({ queryKey: ['connections'] });
  };
}

export function useSaveAppCredentials() {
  const invalidate = useInvalidateCredentialQueries();
  return useMutation({
    mutationFn: async ({ platform, client_id, client_secret, developer_token }: SaveCredentialsInput) => {
      const res = await apiClient.put<ApiResponse<AppCredentialStatus>>(
        `/platform-credentials/${platform}`,
        { client_id, client_secret, developer_token }
      );
      return res.data.data;
    },
    onSuccess: invalidate,
  });
}

export function useDeleteAppCredentials() {
  const invalidate = useInvalidateCredentialQueries();
  return useMutation({
    mutationFn: async (platform: AdPlatform) => {
      await apiClient.delete(`/platform-credentials/${platform}`);
    },
    onSuccess: invalidate,
  });
}
```

- [ ] **Step 4: Run to verify GREEN**

Run: `npx vitest run src/api/appCredentials.test.tsx src/api/getApiErrorMessage.test.ts`
Expected: all PASS (6 in getApiErrorMessage file, 2 in appCredentials).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/appCredentials.ts frontend/src/api/appCredentials.test.tsx frontend/src/api/getApiErrorMessage.test.ts
git commit -m "feat(credentials): app-credentials API hooks; typed error code helper"
```

---

### Task 7: `PlatformCredentialsPanel` UI

**Files:**
- Create: `frontend/src/components/integrations/PlatformCredentialsPanel.tsx`
- Modify: `frontend/src/views/operate/IntegrationsHub.tsx` (mount as first Section, ~L201, right after the header `</div>`)
- Test: `frontend/src/components/integrations/PlatformCredentialsPanel.test.tsx`

**Interfaces:**
- Consumes: `useAppCredentials`, `useSaveAppCredentials`, `useDeleteAppCredentials`, `AppCredentialStatus` (Task 6); `useAuth` from `@/contexts/AuthContext`; `Card` from `@/components/primitives/Card`; `useToast`; lucide icons (`Copy`, `KeyRound`, `Trash2`).
- Produces: `<PlatformCredentialsPanel />` — renders nothing for roles below admin; per-platform cards with fields, callback URL + copy, Save/Remove.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/integrations/PlatformCredentialsPanel.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { mockState } = vi.hoisted(() => ({
  mockState: {
    role: 'owner' as string,
    credentials: [] as unknown[],
    saveMutate: vi.fn().mockResolvedValue({}),
  },
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { role: mockState.role } }),
}));
vi.mock('@/api/appCredentials', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useAppCredentials: () => ({
      credentials: mockState.credentials,
      isLoading: false,
      isError: false,
    }),
    useSaveAppCredentials: () => ({
      mutateAsync: mockState.saveMutate,
      isPending: false,
    }),
    useDeleteAppCredentials: () => ({ mutateAsync: vi.fn(), isPending: false }),
  };
});

import { PlatformCredentialsPanel } from './PlatformCredentialsPanel';

const metaStatus = {
  platform: 'meta',
  configured: false,
  source: null,
  client_id: null,
  has_developer_token: false,
  callback_url: 'https://api.example/api/v1/oauth/meta/callback',
};

beforeEach(() => {
  vi.clearAllMocks();
  mockState.role = 'owner';
  mockState.credentials = [metaStatus];
});

describe('PlatformCredentialsPanel', () => {
  it('renders nothing for roles below admin', () => {
    mockState.role = 'manager';
    const { container } = render(<PlatformCredentialsPanel />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the callback URL for registration', () => {
    render(<PlatformCredentialsPanel />);
    expect(
      screen.getByText('https://api.example/api/v1/oauth/meta/callback')
    ).toBeInTheDocument();
  });

  it('saves entered credentials', async () => {
    render(<PlatformCredentialsPanel />);
    fireEvent.change(screen.getByLabelText(/meta.*app id/i), {
      target: { value: 'cid-1' },
    });
    fireEvent.change(screen.getByLabelText(/meta.*app secret/i), {
      target: { value: 'sec-1' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save meta/i }));
    await waitFor(() =>
      expect(mockState.saveMutate).toHaveBeenCalledWith({
        platform: 'meta',
        client_id: 'cid-1',
        client_secret: 'sec-1',
        developer_token: undefined,
      })
    );
  });
});
```

- [ ] **Step 2: Run to verify RED**

Run: `npx vitest run src/components/integrations/PlatformCredentialsPanel.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the panel**

```tsx
// frontend/src/components/integrations/PlatformCredentialsPanel.tsx
/**
 * Owner/admin panel: per-deployment OAuth app credentials for ad platforms.
 *
 * Black-box model: each customer registers their own developer app per
 * platform and pastes its credentials here (encrypted at rest server-side;
 * secrets are write-only). The callback URL shown per platform must be
 * registered in that platform's developer console.
 */

import { useState } from 'react';
import { Copy, KeyRound, Trash2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import {
  AppCredentialStatus,
  useAppCredentials,
  useDeleteAppCredentials,
  useSaveAppCredentials,
} from '@/api/appCredentials';
import type { AdPlatform } from '@/api/connections';
import { getApiErrorMessage } from '@/api/client';
import { Card } from '@/components/primitives/Card';
import { useToast } from '@/components/ui/use-toast';

const PLATFORM_META: Record<
  AdPlatform,
  { label: string; idLabel: string; secretLabel: string; hasDevToken: boolean }
> = {
  meta: { label: 'Meta', idLabel: 'App ID', secretLabel: 'App secret', hasDevToken: false },
  google: { label: 'Google Ads', idLabel: 'Client ID', secretLabel: 'Client secret', hasDevToken: true },
  tiktok: { label: 'TikTok', idLabel: 'App ID', secretLabel: 'App secret', hasDevToken: false },
  snapchat: { label: 'Snapchat', idLabel: 'Client ID', secretLabel: 'Client secret', hasDevToken: false },
};

function CredentialCard({ status }: { status: AppCredentialStatus }) {
  const meta = PLATFORM_META[status.platform];
  const { toast } = useToast();
  const save = useSaveAppCredentials();
  const remove = useDeleteAppCredentials();
  const [clientId, setClientId] = useState(status.client_id ?? '');
  const [clientSecret, setClientSecret] = useState('');
  const [developerToken, setDeveloperToken] = useState('');
  const [copied, setCopied] = useState(false);

  const sourceLabel =
    status.source === 'database'
      ? 'Configured'
      : status.source === 'environment'
        ? 'Configured via server environment'
        : 'Not configured';

  const handleCopy = async () => {
    await navigator.clipboard.writeText(status.callback_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const handleSave = async () => {
    try {
      await save.mutateAsync({
        platform: status.platform,
        client_id: clientId.trim(),
        client_secret: clientSecret.trim() || undefined,
        developer_token: meta.hasDevToken
          ? developerToken.trim() || undefined
          : undefined,
      });
      setClientSecret('');
      setDeveloperToken('');
      toast({ title: `${meta.label} credentials saved` });
    } catch (error) {
      toast({
        title: `Couldn't save ${meta.label} credentials`,
        description: getApiErrorMessage(error),
        variant: 'destructive',
      });
    }
  };

  const handleRemove = async () => {
    try {
      await remove.mutateAsync(status.platform);
      toast({ title: `${meta.label} credentials removed` });
    } catch (error) {
      toast({
        title: `Couldn't remove ${meta.label} credentials`,
        description: getApiErrorMessage(error),
        variant: 'destructive',
      });
    }
  };

  const idInputId = `${status.platform}-client-id`;
  const secretInputId = `${status.platform}-client-secret`;
  const devInputId = `${status.platform}-developer-token`;

  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-medium text-foreground">{meta.label}</h3>
        <span className="text-xs text-muted-foreground">{sourceLabel}</span>
      </div>

      <div className="space-y-3">
        <div>
          <label htmlFor={idInputId} className="block text-xs text-muted-foreground mb-1">
            {meta.label} {meta.idLabel}
          </label>
          <input
            id={idInputId}
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            autoComplete="off"
          />
        </div>
        <div>
          <label htmlFor={secretInputId} className="block text-xs text-muted-foreground mb-1">
            {meta.label} {meta.secretLabel}
          </label>
          <input
            id={secretInputId}
            type="password"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            placeholder={status.source === 'database' ? '••••••• saved' : ''}
            className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
            autoComplete="new-password"
          />
        </div>
        {meta.hasDevToken && (
          <div>
            <label htmlFor={devInputId} className="block text-xs text-muted-foreground mb-1">
              Developer token
            </label>
            <input
              id={devInputId}
              type="password"
              value={developerToken}
              onChange={(e) => setDeveloperToken(e.target.value)}
              placeholder={status.has_developer_token ? '••••••• saved' : ''}
              className="w-full rounded-xl border border-border bg-card px-3 py-2 text-sm"
              autoComplete="new-password"
            />
          </div>
        )}
      </div>

      <div className="rounded-xl bg-muted px-3 py-2">
        <p className="text-[11px] text-muted-foreground mb-1">
          Register this callback URL in your {meta.label} developer app:
        </p>
        <div className="flex items-center gap-2">
          <code className="text-xs text-foreground break-all flex-1">
            {status.callback_url}
          </code>
          <button
            type="button"
            onClick={handleCopy}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            aria-label={`Copy ${meta.label} callback URL`}
          >
            <Copy className="w-3.5 h-3.5" />
          </button>
          {copied && <span className="text-xs text-primary">Copied</span>}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={save.isPending || !clientId.trim()}
          className="rounded-full px-4 py-1.5 text-sm font-medium bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          Save {meta.label}
        </button>
        {status.source === 'database' && (
          <button
            type="button"
            onClick={handleRemove}
            disabled={remove.isPending}
            className="rounded-full px-3 py-1.5 text-sm text-muted-foreground hover:text-destructive inline-flex items-center gap-1"
          >
            <Trash2 className="w-3.5 h-3.5" /> Remove
          </button>
        )}
      </div>
      {status.source === 'database' && (
        <p className="text-[11px] text-muted-foreground">
          Removing stored credentials does not disconnect already-connected
          accounts.
        </p>
      )}
    </Card>
  );
}

export function PlatformCredentialsPanel() {
  const { user } = useAuth();
  const { credentials, isLoading, isError } = useAppCredentials(
    user?.role === 'owner' || user?.role === 'admin'
  );

  if (user?.role !== 'owner' && user?.role !== 'admin') return null;
  if (isLoading || isError || credentials.length === 0) return null;

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <KeyRound className="w-4 h-4 text-primary" />
          Platform app credentials
        </h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          One-time setup per platform: create a developer app on the platform,
          register the callback URL below, then paste its credentials here.
          Stored encrypted; secrets are never shown again.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {credentials.map((c) => (
          <CredentialCard key={c.platform} status={c} />
        ))}
      </div>
    </section>
  );
}
```

NOTE: check `Card`'s import style (`import { Card } from '@/components/primitives/Card'` vs default export) against IntegrationsHub L33 and match it.

- [ ] **Step 4: Mount in IntegrationsHub**

In `IntegrationsHub.tsx`, import `{ PlatformCredentialsPanel } from '@/components/integrations/PlatformCredentialsPanel'` and render it immediately after the header block's closing `</div>` (~L201), BEFORE the "Ad Platforms" `<Section>`:

```tsx
<PlatformCredentialsPanel />
```

- [ ] **Step 5: Run tests + build**

Run: `npx vitest run src/components/integrations/PlatformCredentialsPanel.test.tsx` → 3 PASS.
Run: `npm run build` → clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/integrations/PlatformCredentialsPanel.tsx frontend/src/components/integrations/PlatformCredentialsPanel.test.tsx frontend/src/views/operate/IntegrationsHub.tsx
git commit -m "feat(credentials): owner/admin platform credentials panel in Integrations"
```

---

### Task 8: Credential-aware Connect callouts (wizard + hub)

**Files:**
- Modify: `frontend/src/views/Onboarding.tsx` (`handleConnectPlatform`, L228-250; callout render in step 2)
- Modify: `frontend/src/views/operate/IntegrationsHub.tsx` (`handleConnect`, L129-143)
- Test: extend `frontend/src/views/Onboarding.step2.test.tsx`

**Interfaces:**
- Consumes: `getApiErrorCode`, `getApiErrorMessage` (Task 6), `CREDENTIALS_NOT_CONFIGURED` (Task 6), `useAuth`.
- Produces: on a `credentials_not_configured` 400, the wizard shows an inline callout (admins: link to `/dashboard/settings/integrations`; others: "ask your organization owner"); IntegrationsHub shows a toast with the real message + the panel is on the same page.

- [ ] **Step 1: Write the failing test** (append to `Onboarding.step2.test.tsx`; reuse its mocks — `startOAuthConnectMock`, `renderWizard`; the file already mocks `@/api/connections`. Add an AuthContext mock alongside the existing ones if not present, defaulting role to `'owner'`.)

```tsx
it('credentials-missing error shows setup callout instead of generic toast', async () => {
  const err = {
    isAxiosError: true,
    name: 'AxiosError',
    message: 'Request failed with status code 400',
    response: {
      status: 400,
      data: {
        detail: {
          code: 'credentials_not_configured',
          message: 'Meta app credentials are not configured. An owner or admin can add them under Settings → Integrations.',
        },
      },
    },
  };
  startOAuthConnectMock.mockRejectedValueOnce(err);
  renderWizard();
  const buttons = await screen.findAllByRole('button', { name: /^connect$/i });
  fireEvent.click(buttons[0]);
  expect(
    await screen.findByText(/app credentials are not configured/i)
  ).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /set up credentials/i })).toHaveAttribute(
    'href',
    '/dashboard/settings/integrations'
  );
});
```

- [ ] **Step 2: Run to verify RED**

Run: `npx vitest run src/views/Onboarding.step2.test.tsx`
Expected: new test FAILS (generic toast path, no callout).

- [ ] **Step 3: Implement**

3a. `Onboarding.tsx` — add state and imports:

```tsx
import { getApiErrorCode, getApiErrorMessage } from '@/api/client';
import { CREDENTIALS_NOT_CONFIGURED } from '@/api/appCredentials';
import { useAuth } from '@/contexts/AuthContext';
// in the component:
const { user } = useAuth();
const isAdmin = user?.role === 'owner' || user?.role === 'admin';
const [credsCallout, setCredsCallout] = useState<string | null>(null);
```

Replace `handleConnectPlatform` (keep structure, change the failure paths):

```tsx
const handleConnectPlatform = async (platform: AdPlatform) => {
  setConnectingPlatform(platform);
  setCredsCallout(null);
  try {
    const url = await startOAuthConnect(platform, '/onboarding');
    if (url) {
      window.location.assign(url);
      return;
    }
    toast({
      title: 'Connection unavailable',
      description: 'Could not start the connection. Try again or continue without connecting.',
      variant: 'destructive',
    });
  } catch (error) {
    if (getApiErrorCode(error) === CREDENTIALS_NOT_CONFIGURED) {
      setCredsCallout(getApiErrorMessage(error));
    } else {
      toast({
        title: 'Connection failed',
        description: getApiErrorMessage(
          error,
          'Could not start the connection. Try again or continue without connecting.'
        ),
        variant: 'destructive',
      });
    }
  } finally {
    setConnectingPlatform(null);
  }
};
```

In the step-2 render block, directly ABOVE the platforms grid, add:

```tsx
{credsCallout && (
  <div
    role="status"
    className="mb-4 flex items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm"
  >
    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-warning" />
    <div className="flex-1">
      <p className="text-foreground">{credsCallout}</p>
      {isAdmin ? (
        <Link
          to="/dashboard/settings/integrations"
          className="mt-1 inline-block font-medium text-primary hover:underline"
        >
          Set up credentials →
        </Link>
      ) : (
        <p className="mt-1 text-muted-foreground">
          Ask your organization owner to configure this platform.
        </p>
      )}
    </div>
  </div>
)}
```

(`AlertCircle` and `Link` are already imported in this file — verify.)

3b. `IntegrationsHub.tsx` — replace `handleConnect`'s silent catch:

```tsx
} catch (error) {
  toast({
    title: 'Connection failed',
    description: getApiErrorMessage(error),
    variant: 'destructive',
  });
  await fetchStatuses();
}
```

adding `const { toast } = useToast();` and the `getApiErrorMessage` import if absent (the credentials panel from Task 7 sits on the same page, so the message's "Settings → Integrations" guidance is self-fulfilling here).

- [ ] **Step 4: Run tests**

Run: `npx vitest run src/views/Onboarding.step2.test.tsx` → all pass (5 tests).
Run: `npm run build` → clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/Onboarding.tsx frontend/src/views/operate/IntegrationsHub.tsx frontend/src/views/Onboarding.step2.test.tsx
git commit -m "feat(credentials): guided callouts when platform credentials are missing"
```

---

### Task 9: Run-once wizard — role-gated guard + view

**Files:**
- Modify: `frontend/src/components/auth/OnboardingGuard.tsx`
- Modify: `frontend/src/views/Onboarding.tsx` (non-admin direct visits bounce)
- Test: `frontend/src/components/auth/OnboardingGuard.test.tsx` (create)

**Interfaces:**
- Consumes: `useAuth().user?.role`; existing `useOnboardingCheck`.
- Produces: only `owner`/`admin` are redirected to `/onboarding` while org onboarding is required; other roles pass straight through; non-admins visiting `/onboarding` directly are sent to `/dashboard/overview`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/auth/OnboardingGuard.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

const { mockState } = vi.hoisted(() => ({
  mockState: { role: 'owner' as string, required: true },
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { role: mockState.role } }),
}));
vi.mock('@/api/onboarding', () => ({
  useOnboardingCheck: () => ({
    data: { required: mockState.required, redirect_to: null },
    isLoading: false,
    error: null,
  }),
}));

import OnboardingGuard from './OnboardingGuard';

function renderGuarded() {
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route
          path="/dashboard"
          element={
            <OnboardingGuard>
              <div>DASHBOARD</div>
            </OnboardingGuard>
          }
        />
        <Route path="/onboarding" element={<div>WIZARD</div>} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  mockState.role = 'owner';
  mockState.required = true;
});

describe('OnboardingGuard role gating', () => {
  it('redirects owner to the wizard while onboarding is required', () => {
    renderGuarded();
    expect(screen.getByText('WIZARD')).toBeInTheDocument();
  });

  it('redirects admin too', () => {
    mockState.role = 'admin';
    renderGuarded();
    expect(screen.getByText('WIZARD')).toBeInTheDocument();
  });

  it.each(['manager', 'analyst', 'viewer'])(
    'lets %s through even while onboarding is required',
    (role) => {
      mockState.role = role;
      renderGuarded();
      expect(screen.getByText('DASHBOARD')).toBeInTheDocument();
    }
  );

  it('lets everyone through once onboarding is done', () => {
    mockState.required = false;
    mockState.role = 'viewer';
    renderGuarded();
    expect(screen.getByText('DASHBOARD')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify RED**

Run: `npx vitest run src/components/auth/OnboardingGuard.test.tsx`
Expected: the `manager/analyst/viewer` cases FAIL (currently redirected to WIZARD).

- [ ] **Step 3: Implement**

In `OnboardingGuard.tsx`: import `useAuth`, compute the gate before the redirect:

```tsx
const { user } = useAuth();
const canRunSetup = user?.role === 'owner' || user?.role === 'admin';
// ...existing loading / error / skip-flag branches unchanged...
if (data?.required && canRunSetup) {
  return <Navigate to="/onboarding" state={{ from: location }} replace />;
}
return <>{children}</>;
```

In `Onboarding.tsx` (top of the component render path, right after the hooks — before `statusLoading` branch):

```tsx
const { user } = useAuth(); // already added in Task 8
if (user && user.role !== 'owner' && user.role !== 'admin') {
  return <Navigate to="/dashboard/overview" replace />;
}
```

(`Navigate` needs importing from `react-router-dom` alongside the existing imports.)

- [ ] **Step 4: Run tests**

Run: `npx vitest run src/components/auth/OnboardingGuard.test.tsx src/views/Onboarding.step2.test.tsx` → all pass (step-2 tests mock role `owner`, unaffected).
Run: `npm run build` → clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/auth/OnboardingGuard.tsx frontend/src/views/Onboarding.tsx frontend/src/components/auth/OnboardingGuard.test.tsx
git commit -m "feat(setup): run-once wizard gated to owner/admin roles"
```

---

### Task 10: Full verification + integrate

- [ ] **Step 1: Backend suite**

Run (from `backend/`): `python -m pytest tests/unit -q`
Expected: pass rate matches baseline (known `test_global_uniqueness.py` env errors are pre-existing).

- [ ] **Step 2: Frontend suite + build**

Run (from `frontend/`): `npx vitest run` → all pass except the known pre-existing `dashboardViews` smoke-test load flake (verify it passes in isolation if it fails: `npx vitest run src/views/__smoke__/dashboardViews.test.tsx`).
Run: `npm run build` → clean.

- [ ] **Step 3: Migration sanity**

Run (from `backend/`, against the local dockerized Postgres if configured): `python -m alembic upgrade head` then `python -m alembic downgrade -1` then `upgrade head` again — or, if no local DB is available, at minimum `python -m alembic check`/`history` to confirm the chain is linear (`b7e3f4a9c2d1 → c8d2e5f7a1b3`).

- [ ] **Step 4: Integration decision**

Use superpowers:finishing-a-development-branch (branch → merge/PR per the user's choice). Note for deploy: Railway runs migrations on release (`start.sh` — verify; if not, run the migration against prod DB deliberately).

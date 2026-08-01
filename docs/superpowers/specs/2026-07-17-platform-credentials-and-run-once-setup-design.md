# Platform App Credentials Manager + Run-Once Setup — Design

**Date:** 2026-07-17
**Status:** Approved (Option A + role-gated run-once wizard; black-box deployment model)

## Business context (drives every decision here)

ADs Growth System is sold as a **black-box, single-client deployment**: each customer
gets their own copy on their own server/domain. The vendor configures only
infra-level env at deploy time (domains, DB, email, superadmin seed). The
customer's owner then performs **first-run setup exactly once** through the
onboarding wizard — including ad-platform app credentials — with no server
access ever required. Invited team members never see setup.

## Problems today

1. Ad-platform OAuth app credentials (Meta app ID/secret, Google client
   ID/secret + developer token, TikTok, Snapchat) are **env-vars only**
   (`core/config.py`: `meta_app_id` etc., default None). A black-box customer
   cannot self-serve; Connect fails with a raw 500
   (`ValueError("Meta App ID not configured")` in `services/oauth/*.py`).
2. The onboarding wizard redirects **every** user while org onboarding is
   incomplete (`GET /onboarding/check` is org-level; `OnboardingGuard` is
   role-blind). A non-admin invitee lands in a wizard whose `/oauth/*` calls
   403 (`require_admin`).
3. The console `/console/credentials` page is presence-only over env vars —
   correct behavior, but it must also reflect DB-stored credentials once they
   exist.

## Component 1: `PlatformAppCredential` storage (backend)

- New model `PlatformAppCredential` (`backend/app/models/platform_app_credential.py`),
  table `platform_app_credential`, one row per platform
  (UniqueConstraint on `platform`, mirroring `platform_connection`):
  - `platform` (String, meta|google|tiktok|snapchat)
  - `client_id` (String, plaintext — it is public in OAuth URLs anyway)
  - `client_secret_encrypted` (Text, Fernet via existing `encrypt_pii`)
  - `developer_token_encrypted` (Text, nullable — Google only)
  - `updated_by_user_id`, `created_at`, `updated_at`
- Alembic migration appended to the existing chain.
- **Resolution order** (new helper `get_platform_app_credentials(platform, db)`
  in `services/oauth/credentials.py`): DB row first → env settings fallback →
  raise a typed `CredentialsNotConfigured` error. OAuth services
  (`base.py` + the four platform services) receive credentials via this
  helper instead of reading `settings.*` directly; the factory
  (`get_oauth_service`) becomes async-aware / takes the resolved credentials.
- The authorize endpoint catches `CredentialsNotConfigured` and returns
  **HTTP 400** with detail exactly:
  `"{Platform} app credentials are not configured. An owner or admin can add them under Settings → Integrations."`
  (No more 500 ValueError.)

## Component 2: Credentials CRUD API (backend)

`backend/app/api/v1/endpoints/platform_credentials.py`, prefix
`/platform-credentials`, all gated `require_admin()` (owner + admin):

- `GET /platform-credentials` → per platform: `{ platform, configured: bool,
  source: "database" | "environment" | null, client_id: str | null,
  has_developer_token: bool }` — **secrets never returned**.
- `PUT /platform-credentials/{platform}` body
  `{ client_id, client_secret, developer_token? }` (secret required on
  create; on update an empty/omitted secret keeps the stored one).
- `DELETE /platform-credentials/{platform}` — removes the DB row (env
  fallback, if any, then applies again).
- Each item in `GET /platform-credentials` carries its resolved
  `callback_url` (`{oauth_redirect_base_url}/api/v1/oauth/{platform}/callback`)
  — the value each customer must register in their developer app for THEIR
  domain. (Folded into the list response; no separate endpoint.)
- Audit-log every write (existing audit middleware/pattern).

## Component 3: Credentials manager UI (frontend)

Owner/admin-only section at the top of Settings → Integrations
(`IntegrationsHub.tsx` hosts it; new component
`frontend/src/components/integrations/PlatformCredentialsPanel.tsx`):

- One card per platform: status chip (Configured via database / via
  environment / Not configured), the platform's field set, the **callback
  URL** with a copy button, Save / Remove.
- Secrets are write-only inputs (placeholder "••••• saved" when configured);
  `client_id` shown.
- React-Query: `useAppCredentials()` (`['app-credentials']`), invalidated on
  save/delete; save also invalidates `['connections']`.
- Hidden entirely for roles below admin.

## Component 4: Credential-aware Connect (frontend)

- Wizard step 2 and IntegrationsHub `handleConnect`: when authorize fails
  with the Component-1 400, render an inline callout instead of a toast-only
  error: admins get "Platform credentials not set up — **Set up now →**"
  (link `/dashboard/settings/integrations`); non-admins get "Ask your
  organization owner to configure this platform."
  Detection: response status 400 + `detail` containing
  "credentials are not configured" (or a `code: "credentials_not_configured"`
  field added to the error body — implement the code field; string-matching
  is a fallback).

## Component 5: Run-once, role-gated wizard

- `OnboardingGuard`: redirect to `/onboarding` only when
  `user.role === 'owner' || user.role === 'admin'`; other roles pass through
  even while org onboarding is incomplete.
- `/onboarding` route: non-admin visitors are `<Navigate to="/dashboard/overview" replace />`
  (guard inside the Onboarding view or its route wrapper).
- Backend defense in depth: onboarding **write** endpoints
  (`business-profile`, `platform-selection`, `goals-setup`,
  `automation-preferences`, `trust-gate-config`, `skip`, `reset`) require
  admin; `GET /onboarding/status` and `/check` stay available to all
  authenticated users (the guard needs them).
- Org-level once-ness already exists (singleton `OrganizationOnboarding`) —
  unchanged.

## Component 6: Console credentials page

`GET /console/credentials/health`'s ad-platform section reports a platform
as configured when EITHER env or DB credentials exist (uses the Component-1
resolver), with the source indicated. Page stays read-only.

## Error handling

- Authorize with no credentials → typed 400 (Component 1) → guided callout
  (Component 4). Never a raw 500.
- Credential save validates non-empty client_id/secret; Google warns (not
  blocks) when developer_token is missing.
- Deleting DB credentials while a `PlatformConnection` is live does NOT
  disconnect it (tokens already exchanged); the panel shows a caution note.

## Testing

- Backend: model round-trip encryption; resolver precedence (db > env >
  error); CRUD endpoint auth (403 for manager), secret-masking of GET;
  authorize returns typed 400 when unconfigured.
- Frontend: PlatformCredentialsPanel (render matrix by role/source,
  write-only secret, callback URL display); Connect callout on the 400 code
  path (wizard + hub); OnboardingGuard role matrix.
- Existing suites stay green.

## Out of scope

- Per-client licensing/branding of the black box.
- Moving email/superadmin/domain config into the UI (stays deploy-time env).
- CRM/WhatsApp credentials (separate systems).
- A dedicated first-run "installer" page beyond the existing wizard.

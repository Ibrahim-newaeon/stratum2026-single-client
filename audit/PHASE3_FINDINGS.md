# PHASE 3 — AUTHENTICATION & SESSION AUDIT
Audit date: 2026-07-18.

## Scope declared
Login/logout/refresh/reset/verify/expiry end-to-end; JWT payload shape vs pre-conversion tokens; the conversion-rewritten `AuthContextMiddleware` and its bypass/allowlist; cookie scoping; email links; OAuth callbacks; superadmin→owner rename; pre-conversion API-key validity. Healthy = every path completes with no live tenant-context dependency and old-shape tokens fail cleanly. Findings this phase: **4** (0 CRITICAL, 3 MEDIUM, 1 LOW).

## What is HEALTHY (traced, evidence-backed)

- **JWT payload has no tenant claim** and never did carry one post-conversion. Access-token claims = `sub, exp, iat, type=access, role, cms_role` (`core/security.py:98-106`, `auth.py:607-611,952-956`). Refresh = `sub, exp, iat, type=refresh, jti` (`security.py:136-140`). **No `tenant_id`/`org_id` claim** → no downstream consumer misreads a removed field. Confirms glossary claim ("No PII and no tenant claim").
- **Pre-conversion token acceptance**: an old multi-tenant token carrying an extra `tenant_id` claim still decodes and works (extra claims ignored by `jwt.decode`), because auth keys only on `sub`/`role`/`type`. No crash-on-old-shape. Same secret/alg assumed unchanged (HS256, `settings.jwt_secret_key`). **No latent poison-token risk** from payload shape.
- **AUTH-001 token-type + revocation enforcement preserved** through the rewrite (`auth_context.py:92-102`): non-`access` tokens rejected 401 regardless of Redis; blacklist checked; **fails OPEN on Redis outage but logs** `token_blacklist_check_unavailable` (`auth_context.py:165-171`) — documented, intentional, visible (not silent).
- **Refresh flow is correct** (`auth.py:897-970`): validates `type==refresh`, checks blacklist, re-verifies user exists + `is_active` + not deleted against DB, **rotates** (blacklists old refresh before issuing new). Rotation is real.
- **`get_current_user` is fail-closed** (`auth/deps.py`): 401 on missing/invalid `sub`, 401 if user absent, 403 if `is_active` false; refreshes `request.state.role` from **DB** (`deps.py:158`), not the JWT claim. Single-PII-key decrypt has graceful fallback that never returns ciphertext (`deps.py:132-160`).
- **Email links are single-`frontend_url`, no tenant subdomains**: reset `…/reset-password?token=` (`auth.py:1120`), verify `…/verify-email?token=` (`email_service.py:174`), invite `…/accept-invite?token=` (`email_service.py:567`). No per-tenant subdomain interpolation anywhere.
- **OAuth ad-platform callbacks**: middleware allowlists exactly `/api/v1/oauth/{provider}/callback` via `re.fullmatch` (`auth_context.py:182`) — narrow, not a prefix; handler validates Redis-stored `state` (CSRF). Redirect built from `settings.frontend_url` (`oauth.py:275-286`). Sound.
- **Cookie scoping**: app is **stateless-bearer, no auth cookies set** (`set_cookie` count = 0 in auth.py). FE stores tokens in `sessionStorage` + in-memory (`client.ts:23-38`), deliberately not `localStorage`. No wildcard/tenant cookie-domain surface exists to leak.
- **Webhook allowlist narrowed during conversion** (documented at `auth_context.py:185-197`): the old blanket `/api/v1/webhooks/` prefix that swallowed the owner-gated management router was fixed to the two exact SendGrid receiver paths; WhatsApp webhooks matched by their own prefix. This is a conversion **fix**, verified present.
- **superadmin→owner rename**: role string is `"owner"` end-to-end (`is_owner_role` canonical check `permissions.py:552-562`; seeds write `role='owner'` / `UserRole.OWNER` `seed_owner.py:116`, `seed_cms_admin.py:77-91`). `request.state.is_superadmin` naming residue is cosmetic (RESIDUE N-10). Deploy installer still speaks "superadmin" in prompts/`SEED_SUPERADMIN` (`deploy/install.sh`) — UX-label residue, seeds an `owner` row; not a defect.
- **Pre-conversion API keys**: validated by hash lookup with scopes (`auth/api_key.py`), independent of tenancy — old keys still validate. `request.state.role="api_key"` set for shared-service reads (`api_key.py:94-97`).

## FINDINGS

```
FINDING-3-1
Feature:        FEAT-005 / FEAT-007 (RBAC via middleware role default)
Status:         DEGRADED
Severity:       MEDIUM
Confidence:     HIGH
What is broken: Privileged user-management and owner-console-flag routes are gated ONLY on
                request.state.role, which AuthContextMiddleware sets from the JWT *claim*
                (auth_context.py:112,117) and NOT from the live DB row. These routes do not
                depend on get_current_user, so they skip the DB is_active/is_deleted/role
                re-check. PATCH /users/{id} changes a user's role/is_active in the DB but does
                NOT blacklist that user's outstanding access token (users.py:403-485; grep for
                blacklist/revoke = 0 hits). Net: a demoted or deactivated admin keeps full
                admin power on exactly these routes for up to the access-token lifetime
                (30 min, config.py:246).
Root cause:     De-tenanting sweep replaced global-middleware enforcement with inline
                `getattr(request.state, "role", ...)` checks that trust the stale JWT role.
                Sites: users.py:183 (list), 231 (invite), 403 (patch role/active), 485 (delete);
                feature_flags.py:99,124,157,179 (console flags). security.py:427 require_permission
                also trusts state.role for the owner bypass.
Blast radius:   Account takeover persistence: revoking/demoting a compromised admin does not take
                effect on user-management + feature-flag routes until token expiry. A just-demoted
                admin can re-invite themselves / re-escalate / flip feature flags within the window.
Evidence:       auth_context.py:112 `role = jwt_payload.get("role")`; :117 `request.state.role =
                role or "analyst"`. deps.py:158 (the fresh-DB path) is NOT invoked by these routes.
                users.py:403-485 mutates role/is_active with no token revocation. Contrast: refresh
                (auth.py:930-947) DOES re-check is_active against DB.
Fix:            (a) On PATCH /users/{id} role/is_active change and on delete, blacklist the target
                user's active tokens (add jti-set or user-version claim). (b) Convert the role-only
                routes to depend on require_admin()/require_owner() built atop get_current_user so
                the DB row is authoritative, OR have AuthContextMiddleware verify role against DB on
                privileged paths. Preferred: (b) — single source of truth.
Confirm via:    Issue admin token; PATCH that admin to role=analyst via another owner; within 30 min
                call GET /api/v1/users with the original token → currently 200 (should be 403).
```

```
FINDING-3-2
Feature:        FEAT-066 (AI onboarding agent)
Status:         DEGRADED
Severity:       MEDIUM
Confidence:     HIGH
What is broken: onboarding-agent LLM routes are reachable fully unauthenticated. /start and
                /message drive the LLM with no auth (OptionalUserDep never raises), so anonymous
                internet callers can invoke paid LLM generations and create/delete sessions by id.
Root cause:     Pre-conversion these were behind the global-401 middleware; the rewrite made
                everything-not-explicitly-guarded public, and these use OptionalUserDep / no auth.
                Sites: onboarding_agent.py:149 (POST /start), 218 (POST /message), 285 (GET
                /status/{id}), 393 (DELETE /session/{id}), 422 (GET /quick-replies/{state}).
Blast radius:   Cost/abuse + DoS: unmetered anonymous LLM spend; session enumeration/deletion by id
                (no ownership check on /status and /session/{id}).
Evidence:       onboarding_agent.py:149,218 signatures take OptionalUserDep; not in middleware
                PUBLIC_ENDPOINTS allowlist; no rate-limit dep observed on /message. (Contrast:
                /complete/{session_id}:319 correctly requires CurrentUserDep.)
Fix:            If pre-signup use is required, gate /message behind a rate limiter + CAPTCHA/nonce
                and scope /status//session to the creating session token; otherwise require auth.
                At minimum add ownership checks on session-id routes.
Confirm via:    curl -X POST /api/v1/onboarding-agent/message with no Authorization header → currently
                reaches the LLM (should 401 or be rate-limited/nonce-gated).
```

```
FINDING-3-3
Feature:        FEAT-164 (HubSpot integration OAuth)
Status:         DEGRADED
Severity:       MEDIUM
Confidence:     MEDIUM
What is broken: GET /api/v1/integrations/hubspot/callback accepts a `state` query param but never
                validates it against the stored/issued value — exchange_code_for_tokens(code,
                redirect_uri) is called without `state` (integrations.py:214-232). OAuth CSRF: an
                attacker can complete the connect flow and bind their own HubSpot account to the org.
                Separately, POST /integrations/hubspot/webhook (integrations.py:328) only verifies
                the HMAC signature when settings.hubspot_client_secret is set; unset → no auth.
Root cause:     This callback is NOT matched by the middleware's `/api/v1/oauth/*/callback` regex
                (different path root `/integrations/…`), so it reaches the app with role-default
                context and the handler is the only line of defense — but it skips state validation.
                Likely pre-existing (not conversion-caused) but exposed by the same "route is public
                unless guarded" model.
Blast radius:   Cross-account OAuth binding of the single org's HubSpot connection; unauthenticated
                webhook writes if the secret is unconfigured.
Evidence:       integrations.py:214 handler declares `state: str = Query(...)` then calls
                exchange_code_for_tokens(code, redirect_uri) — `state` unused. Contrast: the
                /oauth/*/callback family validates Redis state.
Fix:            Validate `state` against the value stored at connect-initiation (integrations.py:200
                already generates+returns `state`); reject webhook when hubspot_client_secret unset.
Confirm via:    Call the callback with a forged `state` → currently proceeds to token exchange.
```

```
FINDING-3-4
Feature:        FEAT-060 (Changelog API)
Status:         DEGRADED
Severity:       LOW
Confidence:     HIGH
What is broken: GET /api/v1/changelog/{entry_id} (changelog.py:243) returns any entry by id with
                NO is_published filter, to anonymous callers — leaking unpublished/draft changelog
                entries. The sibling list route (changelog.py:114) correctly forces is_published
                for non-admins; the by-id route omits the same guard.
Root cause:     Inconsistent published-gating; route is anonymous-reachable because the global-401
                middleware was removed and changelog reads were made public.
Blast radius:   Low-sensitivity marketing/product content disclosed pre-release (roadmap leak),
                enumerable by sequential id.
Evidence:       changelog.py:243-262 selects by id only; no ChangelogEntry.is_published condition.
                Compare :135-136 in the list handler which appends it.
Fix:            Add `if not is_admin: require entry.is_published else 404` to the by-id handler.
Confirm via:    Create an unpublished entry; GET /api/v1/changelog/{id} unauthenticated → currently 200.
```

## Route-authorization sweep result (all 63 modules)
- **Core protected surface is intact**: campaigns, CDP, autopilot(+enforcement), console, console_analytics, clients, reporting, billing-adjacent, ML, GDPR, compliance, integrations mgmt, platform_credentials, api_keys, webhooks(mgmt), users(/me) — all enforce auth (router-level, per-route, or manual user_id 401).
- **No route admits the `"analyst"` middleware-default role** → the unauth default does not create a privilege bypass on any *gated* route (only the unauthenticated reads in 3-2/3-4).
- Intentional-public routes verified sane: health/metrics/docs, newsletter tracking pixels + unsubscribe, push VAPID key + service-worker.js, mfa validate/check (login-flow, lockout-limited), audit/health+info discovery, programmatic (X-API-Key), cms non-admin + landing-cms.

## Seed P3-S1 disposition
`request.state.is_superadmin` "tenancy bypass paths pending Phase C" (`permissions.py:559`, commit `8b0f61fc`): the *flag name* is residue; the bypass behavior it referenced (owner-role bypass) resolves to the `role=="owner"` short-circuit in `require_permission` (`security.py:430`) and `is_owner_role`. **Owner bypass is intentional and role-string based**, not tenant-context based. No dangling tenant-bypass path found. Cleared — but note it inherits FINDING-3-1's stale-role property (owner demotion has the same token-revocation gap).

## Phase 3 summary
Auth core (tokens, refresh rotation, MFA challenge, reset/verify/invite links, OAuth ad-platform callbacks, cookie posture, API keys) is **OPERATIONAL** and cleanly de-tenanted. The systemic weakness is the conversion's chosen pattern — replacing one global-401 middleware with many inline `request.state.role` checks — which introduced (1) a stale-JWT-role privilege-persistence gap on user-management + console-flag routes (3-1) and (2) several routes that silently became public (3-2 LLM abuse, 3-4 content leak). One likely-pre-existing OAuth state gap (3-3). No CRITICAL, no cross-tenant leak (nothing to leak — single org), no auth-bypass on protected routes.

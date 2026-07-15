# Standalone HTML Requirements Page — Design (2026-07-15)

## Goal

A single self-contained HTML artifact rendering the revised v2.1 requirements
(`STRATUM_AI_SINGLE_CLIENT_REBUILD_PROMPT_v2.1_FINAL.md`, commit f443d393) as a
browsable page, sectioned per feature and per platform integration, serving
both stakeholders (plain-language summaries) and engineering (collapsible
technical blocks). Explicit user asks: single page; both audiences; include
required app permissions / OAuth scopes per platform.

## Artifact

- **File:** `STRATUM_AI_REQUIREMENTS_v2.1.html` at repo root (sibling to the
  other report artifacts). Committed to git.
- **Self-contained:** inline CSS + vanilla JS; no CDN, fonts, or images.
  System font stack approximating Geist. Works offline / attached to email.
- **Theme:** ink + ember tokens from `backend/docs/03-frontend/figma-theme.md`
  (dark default, light toggle persisted to localStorage). No glassmorphism.

## Structure

Fixed sidebar (grouped nav, active-section highlight, live text filter) +
content pane. Groups and sections:

1. **Overview** — product summary; Trust Gate flow diagram (pre/ASCII);
   signal-health weight table (EMQ 40 / Freshness 25 / Variance 20 /
   Anomaly 15, CDP 10% carve-out; dashboard heuristic noted); role hierarchy.
2. **Features** — 12 sections mirroring CLAUDE.md's key-feature table: Trust
   Engine, CDP, Autopilot Enforcement, Campaign Builder, Audience Sync,
   Authentication, Analytics, Integrations Hub, CMS, WhatsApp, Reporting,
   Console/Owner.
3. **Platform integrations** — Meta, Google Ads, TikTok, Snapchat, WhatsApp
   Business, CRM (HubSpot + Pipedrive), Comms (Slack + SendGrid/SMTP).
4. **Frontend** — shells, design system, routing, i18n/RTL.
5. **Infrastructure & Ops** — Docker/Railway, CI gates (incl. coverage
   ratchet + residue gate), beat schedule, observability.
6. **Acceptance criteria** — checklist from spec §10 with ratchet wording.

## Section anatomy

Every section: `<h2>` + plain-language **summary card** (what it does, what
the business/client must provide, what's gated), then a `<details>`
**Technical requirements** block: key files, endpoints, env vars, feature
flags (with default-on/off pills), DB tables, acceptance criteria. Platform
sections add a **permissions matrix**: OAuth scopes (source:
`app/services/oauth/*.py` DEFAULT_SCOPES + `campaign_builder.py`
oauth_configs), credential env vars (the names `core/config.py` actually
reads), app-review/approval prerequisites, and related endpoints/workers.

Scopes (verified in code): Meta `ads_management, ads_read,
business_management, pages_read_engagement`; Google
`https://www.googleapis.com/auth/adwords`; TikTok `advertiser.read,
advertiser.write, campaign.read, campaign.write, report.read`; Snapchat
`snapchat-marketing-api`. WhatsApp uses system-user token + webhook verify
token (no OAuth scopes).

## Behavior (JS, ~100 lines)

- Sidebar filter: hides non-matching sections by heading + body text.
- Theme toggle (dark/light), scroll-spy nav highlight, expand/collapse-all
  for the technical blocks, deep-linkable section ids.

## Non-goals

- No generator/build step — hand-authored point-in-time artifact stamped
  "matches spec v2.1 as revised 2026-07-15 (f443d393)".
- No Arabic translation in v1.
- Not served by the app; repo/document artifact only.

## Verification

Open in Chrome; check dark + light, sidebar filter, details toggles, and
spot-check permissions data against `services/oauth/*.py` and `config.py`.

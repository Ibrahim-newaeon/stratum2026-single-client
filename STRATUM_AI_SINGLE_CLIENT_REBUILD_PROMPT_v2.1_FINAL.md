# Build Prompt — Stratum AI Platform (Single-Client Edition, v2.1 FINAL)

> **v2.1 additions:** §4.9 global-uniqueness behavior-change table (+ tests + comment convention), key de-namespacing in §4.8, restored legacy redirects in §5.1, expanded §10 checklist, and optional §12 live-DB conversion track. No scope was removed relative to v2.

> **How to use this prompt:** Give it to a senior full-stack engineering team (or a capable coding agent) as the complete specification for building the **single-client** Stratum AI platform. This document is a 1:1 derivation of the multi-tenant reconstruction spec. **Exactly two categories were removed — nothing else:**
>
> - **(A) Billing & commercial packaging:** Stripe, payments, subscriptions, tier gating, 402 upgrade flows, plans/checkout/pricing pages, white-label editions, licensing.
> - **(B) Multi-tenant partitioning mechanics:** the `Tenant` entity, `tenant_id` columns, tenant middleware/headers, per-tenant encryption keys, tenant provisioning, the tenant-twin frontend shell, cross-*tenant* admin views.
>
> Every other aspect — every endpoint module, model, service, analytics module, worker, view group, design token, infra file, env var, and quirky behavior — is preserved. Follow the pinned versions and build sequencing exactly. Where a section says "match the contract," treat the described behavior as the acceptance criterion.

---

## 0. Role & objective

You are an expert full-stack engineering team building **Stratum AI — Single-Client**, a B2B "Revenue Operating System with Trust-Gated Autopilot" deployed for **one organization** managing its ad accounts across Meta, Google, TikTok, and Snapchat. The organization may internally manage multiple **Brands** (business units / managed accounts) — the agency→brand `Client` model is preserved for this. The defining architectural principle: **automation executes only when signal health passes safety thresholds** — never on degraded data.

Reproduce the system exactly as specified: same stack, same module boundaries, same feature surface, same security model, same design system. Do not introduce new frameworks or abstractions beyond what is listed. Prefer the pinned dependency versions.

Scale target *(estimates — this is a fresh build; original multi-tenant measured counts were 69 / 25 / 61 / 179)*: **~63 API endpoint modules, ~24 SQLAlchemy model modules, fresh Alembic chain 001–0xx, ~140 frontend views**, backend tests in unit + integration tiers with a CI floor guard ratcheted from first-milestone actuals.

### 0.1 Removal ledger (authoritative — the ONLY deletions)

| Removed item | Category | Replacement (if any) |
|---|---|---|
| `Tenant`, `UserTenantMembership` models | B | `Organization` singleton row (identity, branding, thresholds, enforcement mode, onboarding state); users belong directly to the org |
| `TenantMixin` / `tenant_id` columns / tenant-first composite indexes | B | none — indexes drop the tenant prefix (e.g. `ix_campaigns_status`) |
| `TenantMiddleware`, `X-Tenant-ID` header, `require_tenant_id`, `tenancy/` package | B | none — auth middleware only |
| Per-tenant PII keys, `tenant_encryption_keys` table, `encryption.py` model module | B | single app-level `PII_ENCRYPTION_KEY` (Fernet) + documented rotation runbook |
| `TrustGateConfig.from_tenant_settings` | B | `TrustGateConfig.from_org_settings` (reads `Organization` onboarding thresholds) |
| Endpoints: `tenants`, `tenant_dashboard` | B | dashboard endpoints merge into `dashboard` |
| Endpoints: `subscription`, `tier`, `payments`, `stripe_webhook` | A | none |
| `stripe` SDK + `@stripe/react-stripe-js` + `@stripe/stripe-js` | A | none |
| `TierGate`, 402 upgrade-required, `stratum:upgrade-required` event, `UpgradePromptProvider`, `TierContext` | A | `FeatureGate` (env-driven flags) remains the only gating |
| `editions/{starter,professional,enterprise}` + `build.sh` + `SUBSCRIPTION_TIER` + pricing | A | one deployable |
| Tenant provisioning + **licensing** + tier **limits** services (`services/tenant/`), `LICENSE_SIGNING_SECRET` | A/B | org seed script (`seed_superadmin` → `seed_owner`) |
| Frontend shell `/app/:tenantId/*` (`TenantLayout`, the dashboard twin) | B | none — `/dashboard/*` is the single operating shell |
| Console views `TenantsList`, `TenantProfile`, `Billing`; superadmin billing tasks | A/B | none |
| Console view `CrossTenantAnomalies` | B | `CrossAccountAnomalies` (same detection logic across ad accounts/platforms/brands) |
| Public pages `/pricing`, `/plans/:tier`, `/checkout[/success|/cancel]`, checkout views, `plans/` views | A | none |
| Stripe env group (`STRIPE_*`, price IDs) | A | none |
| Beat tasks: billing task submodule | A | none |
| Prometheus tenant-labeled metrics, `request_by_tenant_instrumentation` | B | standard route/status/method labels |
| `superadmin` role name | B | renamed **`owner`** (same level 100, same bypass semantics); `superadmin` endpoints/views renamed `console`/owner-ops |

**Anything not in this table is in scope.** If during the build you find a construct that seems tenant- or billing-shaped but is not listed here, do not delete it — raise it for review.

---

## 1. Core concept — the Trust Gate

```
Signal Health Check  →  Trust Gate  →  Automation Decision
       │                    │                 │
   [HEALTHY  ≥70]       [PASS]            [EXECUTE]
   [DEGRADED 40–69]     [HOLD]            [ALERT ONLY]
   [UNHEALTHY <40]      [BLOCK]           [MANUAL REQUIRED]
```

**Signal Health** is a composite 0–100 score computed from weighted components
(`stratum/core/signal_health.py` `HealthConfig`):

| Component | Weight |
|---|---|
| EMQ (Event Match Quality) | 40% |
| Freshness | 25% |
| Attribution Variance | 20% |
| Anomaly | 15% |

When CDP data is available the four base weights scale by 0.9 and a CDP
component contributes the remaining 10%. The dashboard overview card uses a
separate lightweight heuristic blend (Freshness 40% / EMQ 35% / Connectivity
25%) in `endpoints/dashboard.py` — do not conflate the two.

Thresholds are **org-configurable** (`TrustGateConfig`: pass_threshold 70, hold_threshold 40, high_risk 80, conservative 60; `from_org_settings` reads onboarding thresholds). Enforcement runs in one of three modes: **Advisory**, **Soft-Block**, or **Hard-Block**. `Never auto-execute when signal_health < 70`. Key files to reproduce: `analytics/logic/signal_health.py`, `stratum/core/trust_gate.py`, `autopilot/enforcer.py`.

---

## 2. Tech stack (pin these versions)

### Backend — Python 3.11/3.12
- **Framework:** FastAPI 0.139, Starlette 1.3, Uvicorn 0.50, python-multipart.
- **Async/HTTP:** anyio, httpx 0.28, aiohttp, aiofiles, aiosmtplib, sse-starlette 3.4, sendgrid 6.12.
- **DB:** SQLAlchemy 2.0.51 (async, `asyncpg` 0.31 + `psycopg2-binary` sync), Alembic 1.18, greenlet. PostgreSQL 16 with **pgvector** (`pgvector/pgvector:pg16`).
- **Cache/queue:** Redis 7.4 (`redis[asyncio]` 8.0), Celery 5.6 + Flower 2.0 + celery-redbeat.
- **Auth/security:** PyJWT 2.13, passlib[bcrypt] 1.7.4 with **bcrypt pinned 4.0.1** (5.x breaks hashing), cryptography 48, pydantic[email] 2.13, pydantic-settings 2.14, pyotp 2.10, qrcode[pil].
- **ML/data:** scikit-learn 1.9, pandas 3.0, numpy ≥2.4, scipy, joblib, matplotlib. Optional Vertex AI (`google-cloud-aiplatform`).
- **LLM (optional Copilot paths):** anthropic 0.116, openai 2.44, pgvector 0.5 (RAG embeddings). Default Copilot path is a deterministic keyword classifier — LLM/RAG are opt-in via flags.
- **Ad SDKs:** facebook-business ≥25, google-ads ≥31, requests. *(`stripe` removed — ledger A.)*
- **Scraping (market intel):** beautifulsoup4, lxml.
- **Observability:** structlog 26 (JSON), python-json-logger, sentry-sdk[fastapi] 2.64, prometheus-client, prometheus-fastapi-instrumentator ≥8.
- **Tooling (CI-pinned, run exact versions):** ruff 0.15.x, black 26.5.1, isort 8.0.1, mypy; pytest 9.1, pytest-asyncio, pytest-cov, respx, faker.

### Frontend — Node 20/26
- **Core:** React 19.2, TypeScript 6, Vite 8, react-router-dom 7.18.
- **State/data:** Zustand 5, TanStack Query 5, axios.
- **UI:** Tailwind CSS 3.4 (+ tailwindcss-animate), shadcn/ui vendored on Radix UI primitives, @tremor/react 3, lucide-react + @heroicons/react, class-variance-authority, clsx, tailwind-merge.
- **Viz:** recharts 3.
- **Forms/validation:** react-hook-form 7 + zod 4 + @hookform/resolvers.
- **Editor (CMS):** TipTap 3 (starter-kit, image, link, placeholder).
- **Motion:** framer-motion 12.
- **i18n:** i18next 26 + react-i18next + browser-languagedetector (en + ar wired; RTL support).
- **Other:** @sentry/react, react-helmet-async, react-joyride (product tours), react-grid-layout (custom dashboard), jspdf + html2canvas (PDF export), dompurify, date-fns, embla-carousel, react-countup. *(Stripe React packages removed — ledger A.)*
- **Testing:** Vitest 4 + Testing Library + jsdom; Playwright 1.61 e2e (Chromium/Firefox/WebKit + mobile).
- **Lint:** ESLint 10 flat config (`--max-warnings 0`), Prettier, typescript-eslint.

### Infra
- Docker Compose (7 services), multi-stage Dockerfiles, Nginx reverse proxy, Prometheus + Grafana + Sentry, structlog JSON logging. Primary managed target **Railway**; frontend also on **Vercel**; self-host/beta on DigitalOcean; images to **GHCR**.

---

## 3. Repository layout

```
/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app factory, middleware stack, health/metrics/SSE/WS, lifespan
│   │   ├── base_models.py      # Foundational SQLAlchemy models (Organization, User, Campaign, …)
│   │   ├── api/v1/
│   │   │   ├── __init__.py      # Aggregates all routers into api_router
│   │   │   └── endpoints/       # ~63 endpoint modules
│   │   ├── models/             # ~23 domain model modules (+ base_models.py)
│   │   ├── schemas/            # Pydantic I/O
│   │   ├── services/           # Business logic + external integrations
│   │   ├── analytics/logic/    # ~27 analytics computation modules
│   │   ├── autopilot/          # Action queue + enforcement engine
│   │   ├── stratum/            # Action layer: adapters, trust gate, signal health, workers
│   │   ├── workers/            # Celery app + tasks + beat schedule
│   │   ├── tasks/              # Standalone scheduled rollup tasks
│   │   ├── core/              # config, security, feature gating, logging, metrics, PII key, SSRF, websocket
│   │   ├── auth/               # JWT deps, RBAC permissions, API-key auth
│   │   ├── middleware/         # csrf, rate_limit, security, audit, error_handler, request_logging
│   │   ├── db/                 # session, base, base_class, custom column types
│   │   ├── ml/                 # forecaster, predictors, optimizer, segmenter, ab_testing, explainability, train/inference
│   │   ├── quality/            # trust_layer_service (SignalHealth/AttributionVariance)
│   │   ├── features/           # feature-flag system
│   │   └── monitoring/         # celery hooks, memory audit, visualizations
│   ├── migrations/versions/    # Alembic — fresh chain numbered 001–0xx
│   ├── tests/                  # unit/ + integration/ + root fixtures
│   ├── docs/                   # Curated docs (shipped in image for Copilot RAG indexer)
│   └── Makefile
├── frontend/
│   └── src/                    # views/ (~140) · components/ · api/ (~50) · hooks/ · stores/ · contexts/ · lib/
├── infrastructure/             # prometheus + grafana provisioning
├── nginx/                      # beta reverse-proxy config
├── monitoring/                 # prometheus alerting rules
├── scripts/                    # deploy, DB init/seed, ML train, codemods
├── docker-compose.yml + .{dev,prod,staging,beta,monitoring}.yml
├── vercel.json
└── CLAUDE.md                   # engineering conventions
```

*(Removed vs original: `app/tenancy/`, `editions/` — ledger. Everything else identical.)*

---

## 4. Backend specification

### 4.1 Data model (SQLAlchemy 2.0, async)

Every business table carries `TimestampMixin` and `SoftDeleteMixin`. **No `TenantMixin`, no `tenant_id`** — composite indexes drop the tenant prefix (e.g. `ix_campaigns_status`). A singleton **`Organization`** row holds org identity, branding, trust-gate thresholds, enforcement mode, and onboarding state. PII is Fernet-encrypted via `EncryptedString` with the single app key, loaded at startup.

Model modules and their entities:

- **`base_models.py`** — `Organization` (singleton), `User`, `Campaign`, `CampaignMetric`, `CreativeAsset`, `Rule`, `RuleExecution`, `CompetitorBenchmark`, `AuditLog`, `APIKey`, `MLPrediction`, `NotificationPreference`, `LandingPageSubscriber`, WhatsApp (Contact, Conversation, Message, Template), and all enums (`UserRole`, `AdPlatform`, `CampaignStatus`, …). *(`Tenant`, `UserTenantMembership` removed — ledger B.)*
- **`attribution.py`** — ConversionPath, ChannelInteraction, AttributionSnapshot, DailyAttributedRevenue, TrainedAttributionModel, ModelTrainingRun.
- **`autopilot.py`** — EnforcementSettings (org-level), EnforcementRule, EnforcementAuditLog, PendingConfirmationToken (+ EnforcementMode/ViolationType/InterventionAction enums).
- **`campaign_builder.py`** — CampaignDraft, CampaignPublishLog, PlatformConnection, AdAccount.
- **`capi_delivery.py`** — CAPI event delivery logs/records.
- **`cdp.py`** — Profiles, segments, computed traits, funnels, identity graph (largest module).
- **`client.py`** — **Client (Brand/business-unit workspace), ClientAssignment, ClientRequest** — same schema and workflows as the agency→brand model, scoped to the single org: the marketing team assigns managers/analysts to Brands, and Brand-side viewers submit requests. Keep even if the org starts with one Brand.
- **`cms.py`** — Blog posts, pages, categories, authors, content.
- **`copilot_doc.py`** — CopilotDocChunk (RAG chunks, `vector(1536)`).
- **`crm.py`** — CRMConnection, CRMContact, CRMDeal, Touchpoint, CRMWritebackConfig/Sync, DailyPipelineMetrics.
- **`drip.py`** — DripSequence, DripExecutionRecord.
- **`embed_widgets.py`** — Embeddable widgets + tokens.
- **`emq_playbook.py`** — EmqPlaybookItemState.
- **`launch_readiness.py`** — LaunchReadinessEvent, LaunchReadinessItemState.
- **`newsletter.py`** — Campaigns/subscribers.
- **`onboarding.py`** — Onboarding wizard state (org setup: connect platforms → thresholds → invite team).
- **`pacing.py`** — Target, DailyKPI, Forecast, PacingAlert, PacingSummary.
- **`profit.py`** — ProductCatalog, ProductMargin, COGSUpload, MarginRule, DailyProfitMetrics, ProfitROASReport.
- **`push.py`** — PushSubscription, PushNotificationLog.
- **`reporting.py`** — ScheduledReport, ReportTemplate, ReportExecution, ReportDelivery, DeliveryChannelConfig.
- **`settings.py`** — Org/app settings.
- **`trust_layer.py`** — FactSignalHealthDaily, FactAttributionVarianceDaily, FactActionsQueue (fact tables).
- **`audit_services.py`** — EMQ/offline-conversion/A-B/LTV audit records.
- **`audience_sync.py`** — PlatformAudience sync configs/schedules.

*(Removed vs original: `encryption.py` per-tenant key storage — ledger B. All other modules retained.)*

**⚠️ Global-uniqueness behavior changes (enforce explicitly).** Every former composite `UNIQUE(tenant_id, x)` becomes `UNIQUE(x)` — this silently changes runtime behavior and MUST be flagged and tested, not just migrated. Known affected constraints (audit for more during Milestone 1):

| Column(s) | Old scope | New behavior |
|---|---|---|
| `users.email` | unique per tenant | **globally unique** — same email can no longer exist twice |
| `api_keys.key_hash` | unique per tenant | globally unique |
| `campaigns(platform, external_id)` | unique per tenant | globally unique per platform |
| `cms` slugs (posts/pages/categories) | unique per tenant | globally unique |
| `newsletter` subscriber email | unique per tenant | globally unique per list |
| `cdp` identity keys (email/phone/external-id hashes) | unique per tenant | globally unique in identity graph |
| `embed_widgets` tokens, `webhooks` endpoint URLs, `reporting` template names, `drip` sequence names, `clients.name` | unique per tenant | globally unique |

Convention: every model/migration line where scope changed carries the inline comment `# was tenant-scoped; now global`. Each converted constraint ships **positive + negative tests** (insert succeeds once; duplicate rejected with the correct 409/422 contract).

### 4.2 API layer (`app/api/v1/endpoints/`, ~63 modules)

Router registration in `app/api/v1/__init__.py` (some routers self-declare prefixes; some feature-gated via `Depends(FeatureGate(Feature.*))`, some `require_owner`). Mounted under `/api/v1`. Endpoint module groups:

- **Auth/users/org:** `auth`, `mfa`, `users`, `organization` (settings singleton), `clients` (Brand workspaces). *(`tenants`, `tenant_dashboard`, `subscription`, `tier`, `payments`, `stripe_webhook` removed — ledger.)*
- **Campaigns/creative:** `campaigns`, `campaign_builder`, `assets`, `rules`, `simulator`.
- **Analytics/AI:** `analytics`, `analytics_ai`, `advanced_analytics`, `dashboard`, `insights`, `intelligence`, `predictions`, `ml_training`, `copilot`, `knowledge_graph`.
- **Attribution/measurement:** `attribution`, `data_driven_attribution`, `capi`, `meta_capi`, `emq_v2`, `qa_fixes`, `trust_layer`.
- **Autopilot:** `autopilot`, `autopilot_enforcement`.
- **Pacing/profit/reporting:** `pacing`, `profit`, `reporting`, `audit_services`.
- **CDP/CRM:** `cdp`, `audience_sync`, `integrations`, `outbound_integrations`.
- **Messaging/notifications:** `whatsapp`, `newsletter`, `drip_campaigns`, `push_notifications`, `notifications`, `slack`, `sendgrid_webhook`.
- **Content/marketing:** `cms`, `landing_cms`, `competitors`.
- **Platform/admin:** `oauth`, `console` (renamed from `superadmin`), `console_analytics` (renamed from `superadmin_analytics`; platform-usage analytics of this deployment, no cross-tenant scope), `launch_readiness`, `feature_flags`, `onboarding`, `onboarding_agent`, `changelog`, `compliance`, `gdpr`, `developer`, `api_keys`, `programmatic`, `webhooks`, `embed_widgets`, `memory_debug`.

**Endpoint contract (enforce on every route):** auth dependency present; Pydantic schemas for all I/O; audit log on state-changing requests; rate limit; async/await for all I/O; type hints on all functions. *(The tenant-scoping dependency does not exist — do not reintroduce it. Owner-only replaces superadmin-only for raw-SQL/global-list/debug endpoints.)*

### 4.3 Services layer (`app/services/`)

Packages: `oauth/` (base/factory + google/meta/tiktok/snapchat authorization flows), `pacing/` (pacing_service, forecasting, alert_service), `profit/` (profit/cogs/product), `reporting/` (report_generator, pdf_generator, delivery, scheduler), `crm/` (per-provider client/sync/writeback for HubSpot/Pipedrive/Salesforce/Zoho + identity_matching), `cdp/` (segment, identity_resolution, computed_traits, funnel + `audience_sync/`), `attribution/` (attribution_service, journey, **markov_attribution**, **shapley_attribution**, model_training), `capi/` (capi_service, platform_connectors, event_mapper, pii_hasher, data_quality, distributed_dedupe, dead_letter_queue, delivery_logger), `agents/` (root_agent, copilot_agent keyword classifier, copilot_llm[_stream], doc_index, greeting_tool), `sync/` (orchestrator + meta/tiktok/snapchat ingestion), `notifications/` (slack_service), `knowledge_graph/` (Apache AGE — flagged off), `embed_widgets/`.

Top-level services: `emq_service`, `emq_measurement_service`, `cdp_emq_aggregator`, `offline_conversion_service`, `conversion_latency_service`, `creative_performance_service`, `competitor_benchmarking_service`, `competitor_scraper`, `audience_insights_service`, `budget_reallocation_service`, `rules_engine`, `circuit_breaker`, `market_proxy`, `mfa_service`, `email_service`, `storage`, `encryption`, `whatsapp_client`, `whatsapp_service`, `mock_client`.

*(Removed vs original: `stripe_service`; `tenant/` provisioning/licensing/limits — ledger. All other services retained.)*

### 4.4 Analytics, ML, Autopilot/Trust engine

- **`analytics/logic/` (~27 modules):** scoring, recommend, anomalies (Z-score) + anomaly_narratives, fatigue, budget + predictive_budget, creative_scoring, cross_platform_optimizer, attribution + attribution_confidence, journey_mapping, ab_test_analysis, churn_prevention, ltv_forecasting, audience_lifecycle, signal_health, signal_recovery, emq_calculation, goal_tracking, competitor_intel, collaborative_annotations, nl_filters, ai_reports, knowledge_graph, unified_notifications, types.
- **`ml/`:** forecaster, conversion_predictor, ltv_predictor, roas_optimizer, rfm_segmenter, creative_lifecycle, ab_testing, ab_power_analysis, explainability (SHAP), simulator, train/inference/retraining_pipeline, data_loader, integrity. **ML models are pre-trained at Docker build time** (`scripts/build_ml_models.py`) to avoid ~9.5 GB runtime training.
- **Autopilot:** `autopilot/service.py` (`AutopilotService`: queue actions to `FactActionsQueue`, `can_auto_execute` trust-gate check, approve/dismiss/apply, `process_recommendations_to_actions`). `autopilot/enforcer.py` (`AutopilotEnforcer`: budget/ROAS/frequency guardrails, `check_action`, `confirm_action`, `auto_pause_campaign`, kill-switch, freeze).
- **Trust gate:** `stratum/core/trust_gate.py` (`TrustGate` + `TrustGateConfig`, `GateDecision`, `TrustGateResult.evaluate()`), `stratum/core/signal_health.py`, `stratum/core/autopilot.py`. Dashboard cards via `quality/trust_layer_service.py`.
- **Stratum adapters:** `stratum/adapters/` (meta/google/tiktok/snapchat/whatsapp + `registry.py` populated at startup via `register_default_adapters()`, `base.py`). Workers: `stratum/workers/` automation_runner, data_sync.

### 4.5 Auth & security model (reproduce exactly, minus tenancy)

- **Authorization is user + role + Brand assignment.** No `X-Tenant-ID` header, no tenant claim, no tenant middleware. Brand-level access control uses `ClientAssignment` (managers/analysts see assigned Brands; owner/admin see all).
- **JWT + refresh:** bcrypt (72-byte truncation), JWT HS256, refresh rotation + **Redis blacklist** (`is_token_blacklisted`); middleware rejects non-`access` token types and revoked tokens, **failing open if Redis is down** (blacklist unavailable) while still rejecting wrong token types. Login lockout after N failures. **No PII in JWT claims.**
- **MFA (TOTP) enforced at login:** stateless challenge-exchange `/api/v1/auth/login` → `/api/v1/auth/login/mfa` (self-authenticates via `mfa_token` challenge); backup codes supported.
- **RBAC (`auth/permissions.py`):** `PermLevel` int-comparable resource levels; granular `Permission` enum (USER_*, CAMPAIGN_*, ANALYTICS_*, SYSTEM_*, CONNECTOR_*, AUDIT_*, ALERT_*, ASSET_*, RULE_*, CLIENT_*…; **drop TENANT_\* and BILLING_\*** — ledger); `ROLE_PERMISSIONS` per role. Role hierarchy: **owner 100, admin 80, manager 50, analyst 30, viewer 10** (mirror on frontend; `owner` replaces `superadmin` with identical semantics incl. scoping bypass). `auth/deps.py` provides `get_current_user/active/verified`, `require_role(*roles)`, `require_admin/owner`, CMS auth `get_cms_user`/`require_cms_permission`.
- **API keys:** inbound `X-API-Key` authenticator (`auth/api_key.py`, `APIKeyPrincipal`, `require_api_key_scope`), hashed at rest, `last_used` tracking, scopes (admin scope satisfies any); used by `/programmatic/*` (`/programmatic/whoami`).
- **Feature gating:** `FeatureGate` (env-driven flags) on flagged routers. *(Tier/subscription gating and 402 removed — ledger A.)*
- **Secrets at rest:** Fernet-encrypted PII + connector secrets via `EncryptedString` column type; single app-level PII key; production guards fail closed on dev-default signing secrets.
- **Audit pipeline:** state-changing requests queued to Redis, persisted by a Celery worker; constant-time comparison via `hmac.compare_digest`.
- **Transport/app:** security-headers middleware, CSRF middleware, webhook signature verification (WhatsApp, SendGrid), SSRF guard on outbound webhooks.

### 4.6 App entrypoint & middleware (`app/main.py`)

- App factory `create_application()`. Prometheus instrumentator added first (standard route/method/status labels). Production docs gate: `/docs`, `/redoc`, `/openapi.json` behind `DOCS_API_KEY` query param.
- **Middleware execution order (outermost→in):** CORS → timing → Security headers → Audit → RateLimit → Gzip → Exception → Router. (CORS outermost so its headers apply to early 401s. Tenant middleware removed from the chain — ledger B.)
- Exception handlers: `StratumError` (structured domain error) + global `Exception` (traceback in dev, generic in prod).
- Routes beyond the API router: `/health`, `/health/ready` (503 until DB+Redis up — Railway probe), `/health/live`, **`/public/demo-metrics`**, **`/public/events/stream` (SSE)**, `/metrics` (bearer-gated), `/api/v1/events/stream` (org SSE via Redis pubsub), `/ws` WebSocket (JWT-verified), `/ws/stats`. Serve frontend SPA from `frontend/dist` if present.
- **Lifespan startup:** Sentry init (prod/staging) → DB health check → WebSocket manager start → ML auto-train if no `.pkl` → register platform adapters → seed owner → load PII key. Shutdown: stop WS manager, dispose engine.

### 4.7 Config (`app/core/config.py`)

Pydantic `Settings`, env-driven, cached via `get_settings()`. Validators: auto-convert `postgres://`→async driver, derive sync URL, warn on weak keys, and **hard-fail in production/staging** on dev-default secrets, mock ad data, or localhost/wildcard CORS. Setting groups (env var names): Application, Database (+ pool tuning), Redis/Celery, ML, Ad platforms (Meta/Google/TikTok/Snapchat), WhatsApp, CRM (HubSpot/Pipedrive), Market intel (SerpAPI/DataForSEO), Security (JWT/PII), CORS, Observability (Sentry/log), Email/SMTP/SendGrid, LLM/Copilot (Anthropic), Copilot RAG (OpenAI embeddings/pgvector), Asset storage (local/S3), Rate limiting, Feature flags. *(Stripe group removed — ledger A.)* See §7 for the full env catalog.

### 4.8 Migrations & workers

- **Key de-namespacing (system-wide):** all tenant-prefixed keys lose the prefix — Redis cache keys (`cache:{tenant}:…` → `cache:…`), rate-limit buckets, Celery task args/routing that carried `tenant_id`, SSE/pubsub channel names, WebSocket rooms, asset storage paths (`assets/{tenant}/…` → `assets/…`), and report/PDF output paths. Grep-audit for `{tenant` patterns in key builders; the CI residue gate (§6.4) covers this.
- **Alembic:** active dir `backend/migrations/versions/`, **fresh chain numbered from 001**. All migrations reversible (up + down) or ship a documented rollback. The pgvector migration (`vector(1536)` for Copilot RAG) must precede `copilot_doc`. Include FK-index and schema-drift-reconciliation discipline from the original (audit indexes on all FKs; reconcile drift with dedicated migrations, never hand-edits). *(No tenant-keys migration — ledger B.)*
- **Celery (`app/workers/celery_app.py`):** Redis broker/backend (DB /1 broker, /2 result). Beat schedule includes: `sync_all_campaigns` (hourly), `generate_daily_forecasts` (06:00), `calculate_all_fatigue_scores` (03:00), `process_audit_log_queue` (every min), `check_pipeline_health` (:30), `worker_heartbeat` (min), `calculate_daily_scores` (04:00), `run_all_predictions` (*/30 — single org, no tenant fan-out), `process_scheduled_whatsapp_messages` (min), plus `app/tasks/*` rollups: apply_actions_queue (*/5), signal_health (02:00), attribution_variance (02:15), audience_auto_sync (*/15). Feature-gated beats: campaign_builder sync/token-refresh/health, newsletter sweep, rules evaluation. Task submodules under `workers/tasks/`: audit, cdp, cms, competitors, creative, forecast, ml, monitoring, rules, scores, sync, whatsapp, helpers. *(billing submodule removed — ledger A.)*

---

## 5. Frontend specification

Vite + React 19 + TypeScript SPA. **Authenticated shells: `/dashboard/*` (operating), `/console/*` (owner ops), `/cms/*`, `/portal/*` (Brand-side viewers).** The tenant-twin shell `/app/:tenantId/*` is removed (ledger B) — it existed only to resolve a tenant from the URL.

### 5.1 Routing (`src/App.tsx`)

Single `<Routes>` tree; every page lazy-loaded via `lazyWithRetry()` (auto-reloads once on chunk-load failure after deploy). Provider nesting (outer→in): `HelmetProvider → ThemeProvider → AuthProvider → DemoProvider → TooltipProvider → JoyrideProvider`. *(`UpgradePromptProvider` removed — ledger A.)* Global: `DocumentDirectionHandler`, `SkipToContent`, `Toaster`, `OfflineIndicator`. Auth wrappers: `ProtectedRoute` (auth + role/permission/portal gating), `CMSProtectedRoute`, `OnboardingGuard`, `ErrorBoundary`, `LazyRoute`.

Route groups:
- **Public:** `/`, `/ar`, `/login`, `/signup` (gated by `ENABLE_PUBLIC_SIGNUP`, default off — invite-only otherwise), `/forgot-password`, `/reset-password`, `/verify-email`, `/accept-invite`, `/cms-login`, `/cdp-calculator`, marketing pages (`/features`, `/integrations`, `/api-docs`, `/solutions/*`, `/about`, `/careers`, `/blog[/:slug]`, `/contact`, `/faq`, legal `/privacy|/terms|/security|/dpa`, `/docs[/*]`, `/changelog`, `/case-studies`, `/resources`, `/status`, `/compare`, `/glossary`, `/announcements/audience-sync`), `/unauthorized`, `*` (404). *(`/pricing`, `/plans/:tier` removed — ledger A.)*
- **`/dashboard/*`** — ProtectedRoute + OnboardingGuard → `DashboardLayout` (~60 child routes; role-gated inline).
- **`/console/*`** — ProtectedRoute `requiredRole="owner"` → `ConsoleLayout` (owner ops shell).
- **`/cms/*`** — CMSProtectedRoute. **`/portal/*`** — ProtectedRoute `portalOnly` (VIEWER users, Brand-scoped). **`/onboarding`** — auth only. *(`/checkout[/success|/cancel]` removed — ledger A.)*
- **Legacy redirects:** `/overview`→`/dashboard/overview`; `/dashboard/superadmin/*`→`/console/*`; `/app/:tenantId/*`→`/dashboard/*` (tenant segment discarded — supports bookmarks when converting an existing deployment).

### 5.2 Views (`src/views/`, ~140 — estimate)

Grouped subfolders: `dashboard/` (Overview + KpiStrip/SignalStrip/FocusPane/RecentAutopilot), `ops/` (33, absorbing the former tenant group: SignalHub, CampaignBuilder, ConnectPlatforms, Pacing, ProfitROAS, Attribution, Reporting, ABTesting, ModelExplainability, EmbedWidgets, AuditLog…), `cdp/` (11: Profiles, Segments, Events, IdentityGraph, AudienceSync, Rfm, Funnels, ComputedTraits, Consent, PredictiveChurn), `console/` (owner ops: ControlTower, FeatureFlags, PlatformAnalytics, Credentials, **CrossAccountAnomalies**, EMQMeasureWorkflow, OfflineConversions, Experiments, BudgetReallocation, LTVBatchPredict, System, Users, LaunchReadiness — merged former console/ + superadmin/ minus TenantsList/TenantProfile/Billing), `cms/` (13), `newsletter/` (6), `whatsapp/` (5), `knowledge-graph/`, `am/` (account manager — Brand management), `portal/`, `pages/` (public marketing incl. `solutions/`, `company/`, `legal/`, `resources/docs/`). Layout shells: DashboardLayout, ConsoleLayout, CMSLayout, PortalLayout. *(`plans/`, `checkout/`, `tenant/` twin removed — ledger.)*

### 5.3 Design system (reproduce tokens exactly)

Brand: **"Bloomberg-density · Apple restraint · ember warmth"** — bold, intelligent, premium; quiet authority; information density without clutter. Anti-reference: enterprise gray, default violet/cyan glassmorphism. **No glassmorphism.**

- **Theme:** dual-mode (figma dark default + coherent figma light). `darkMode: ['class']`. Pre-paint theme set by inline script in `index.html` (reads `localStorage('stratum-theme')`, `theme-no-transition` guard prevents flash); `ThemeProvider` (`dark|light|system`, listens to OS). `ThemeToggle` sun/moon/system in topbar.
- **Tokens (HSL CSS vars in `src/index.css`):** Dark — `--background` `#0B0B0B` ink, `--card` `#141414`, `--surface-tertiary` `#1A1A1A`, `--muted` `#262626`, `--border` `#1F1F1F`, `--foreground` `#FFFFFF`, `--muted-foreground` `#9A9A9A`, `--primary` ember `#FF5A1F`, `--secondary` ember-2 `#FF8A4A`, `--accent`/`--info` cyan `#06B6D4`, `--success` `#10B981`, `--warning` `#F59E0B`, `--danger` `#EF4444`. Light — bg `#FAFAF7`, surface `#FFFFFF`, line `#E8E8E0`, fg `#1A1A1A`, muted-fg `#5A5A55`, primary `#E84F1F`. Plus platform badge colors, glow tokens, full `--landing-*` palette (public site retained).
- **Geometry:** `--radius: 1rem` (16px); radii 8/12/14/16/18px; card padding `p-6` min; buttons/pills `rounded-full`.
- **Typography:** **Geist** (sans + display) + **Geist Mono** (labels/status/tabular) from Google Fonts — the app shell loads only these; **Cairo** (Arabic) is loaded by the static `/landing-ar.html` asset itself (rendered in an iframe by `LandingAr`), not by `index.html`; `font-feature-settings 'ss01','cv11'`; fontSize scale micro 10 → body 14 → display-lg 72px. **No Satoshi/Clash/Inter.**
- **Motion:** keyframes fade-up/delta-pop/sweep/glow-pulse/shimmer/float/orbit; transitions fast 120 / base 200 / slow 350; easing `cubic-bezier(0.16,1,0.3,1)`; full `prefers-reduced-motion` reset.

**Primitive library (`components/primitives/`, each with co-located vitest, ARIA + keyboard first-class):**
- `Card.tsx` — surface, variants `default|elevated|glow`, `Card.Header/Title/Description/Body/Footer`, `interactive` hover-lift.
- `KPI.tsx` — Card + label + value + `delta` (percent/absolute/raw, `invert`) + footnote + StatusPill slot + `emphasis: glow`; loading/empty/error props.
- `StatusPill.tsx` — signature pill `healthy|degraded|unhealthy|neutral`, pulsing glow dot, `role="status" aria-live`.
- `Chart.tsx` — themed recharts wrapper (Line/Area), token-driven colors; loading/empty/error.
- `DataTable.tsx` — headless typed table, custom cell renderers, optional sort, sticky header, keyboard row click; loading/empty/error; external pagination.
- `ConfirmDrawer.tsx` — Radix Dialog preview-then-confirm gate; `default|destructive|warning`.
- `InsightsPanel.tsx` — severity-sorted attention items with CTAs.
- `nav/` — `Sidebar.tsx` + `Topbar.tsx`; **data-driven IA** `dashboardNav.ts` (Operate / Intelligence / Workspace groups + `SIDEBAR_VISIBILITY` role map + `buildDashboardNav(role)`) and `consoleNav.ts` (Platform / Operations / Health). Sidebar auto-expands the active group; collapse state persists per-user.
- `theme/` — ThemeProvider + ThemeToggle.

Plus `components/ui/` (~50 vendored shadcn/radix primitives + app-specific ErrorBoundary, EmptyState, LazyRoute, TrustGateIndicator, command-palette, otp-input, password-strength, phone-input, keyboard-shortcuts) and domain folders (dashboard cards, cdp, widgets, landing, onboarding, guide tours, cms RichTextEditor via TipTap). *(billing components removed — ledger A.)*

### 5.4 State, API layer, i18n

- **Zustand stores:** `appStore` (renamed from tenantStore: user session, `UserRole`, date range, platform filter, **Brand filter**, owner mode/bypass; `devtools + persist`, persists only dateRange/selectedPlatforms/selectedBrand/isOwnerMode — never bypass flags; computed `isOwner/isAdmin/hasRole/hasFeature`), `featureFlagsStore` (flags incl. `autopilot_level` 0–2, `can()`, `getAutopilotLevel()`, `isAutopilotBlocked(signalHealth)`).
- **Contexts:** `AuthContext` (JWT login with retry + 429 lockout + Pydantic error parsing, `loginMfa` second factor, client-side `demoLogin` gated by `VITE_ENABLE_DEMO_MODE`, session restore, role-based idle timeout 15–60 min with warning; syncs to appStore), `DemoContext`, `DashboardSimulationContext`. *(`TierContext` removed — ledger A.)*
- **API (`src/api/`, ~50 axios modules + `hooks/`):** central `client.ts` — base URL `window.__RUNTIME_CONFIG__.VITE_API_URL || import.meta.env.VITE_API_URL || '/api/v1'`, 30s timeout, access token in-memory + sessionStorage. Request interceptor injects `Authorization: Bearer` only (**no `X-Tenant-ID`** — ledger B). Response interceptor: **401 → mutex-guarded refresh via `/auth/refresh`** (queues concurrent 401s; on failure redirect `/login?reason=session_expired`). *(402 upgrade event removed — ledger A.)* React Query hooks in `api/hooks/` (`useDashboard`, `useConsole`, barrel `index.ts`); shared QueryClient (staleTime 5min, retry 1, `refetchOnWindowFocus false`) kept out of `main.tsx` for testability.
- **i18n:** i18next + LanguageDetector, `fallbackLng: 'en'`, wired **en + ar** (the `uk` locale file exists but is **not wired** — reproduce as a dormant asset). **RTL:** `useDocumentDirection` syncs `<html lang/dir>`, `ltr`/`rtl` body class, `--direction`/`--rtl-multiplier` vars; RTL set `['ar','he','fa','ur']`; dedicated `Landing` vs `LandingAr` + `/ar` route.

### 5.5 Build & test config

- **`vite.config.ts`:** `@`→`./src`; dev port 5173 proxy `/api`→`localhost:8000`; build outDir `dist`, no sourcemaps, detailed `manualChunks` (vendor-pdf/react/charts/ui/query/motion/editor/i18n/forms/utils). `index.html` pre-paint theme script + font preloads + `__RUNTIME_CONFIG__`. `main.tsx`: StrictMode → QueryClientProvider → BrowserRouter → App; Sentry init with PII stripping when `VITE_SENTRY_DSN` set. Build script `tsc --noEmit -p tsconfig.build.json && vite build`.
- **Vitest:** jsdom, coverage scoped to components/contexts/hooks/stores (regression-ratchet thresholds). **Playwright:** 5 projects (Chromium/Firefox/WebKit + Mobile Chrome/Safari), specs auth/dashboard/emq/logout/mobile/onboarding/settings/signup-otp/whatsapp + console. *(tenant spec removed — ledger B; signup-otp runs with the signup flag enabled in CI.)*

---

## 6. Infrastructure & DevOps

### 6.1 Docker Compose (base `docker-compose.yml`, 7 services)

Network `stratum_network`; volumes `postgres_data`/`redis_data`; all services with resource limits, json-file logging, healthchecks.

| Service | Image/Build | Port | Notes |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | 5432 | runs `scripts/init-db.sql` |
| `redis` | `redis:7-alpine` | 6379 | appendonly, 256mb LRU, password |
| `api` | build `./backend` | 8000 | non-root `1000:1000`, `no-new-privileges`; entrypoint `start.sh` (DB wait → alembic → seed → uvicorn) |
| `worker` | build `./backend` | — | `celery worker --concurrency=4` |
| `scheduler` | build `./backend` | — | `celery beat` |
| `frontend` | build `./frontend` target `development` | 5173 | `npm run dev --host 0.0.0.0` |
| `flower` | build `./backend` | 5555 | profile `monitoring`, basic-auth |

Redis DB map: `/0` cache, `/1` broker, `/2` result backend.

**Overlays:** `.dev.yml` (frontend-only, host-run backend), `.prod.yml` (`restart: always`, DB/Redis host ports removed, adds **pgbouncer** transaction pooling, tuned Postgres, frontend `target: production` on 80, `alembic upgrade head && uvicorn --workers 4`), `.staging.yml` (self-contained), `.beta.yml` (adds **nginx** via `nginx/beta.conf`, external managed Postgres — DigitalOcean), `.monitoring.yml` (Prometheus :9090 15d retention + Grafana :3001, provisioned).

### 6.2 Dockerfiles

- **`backend/Dockerfile`:** single-stage `python:3.11-slim-bookworm`, non-root `appuser` (uid 1000), installs `requirements-prod.txt` (pip/setuptools/wheel upgraded for CVEs), purges build deps, **pre-trains ML models at build** (`scripts/build_ml_models.py`), `HEALTHCHECK /health/ready`, entrypoint `/app/start.sh`. Build context `backend/` (ships `backend/docs/` for Copilot RAG corpus).
- **`frontend/Dockerfile`:** multi-stage `node:26-alpine` — `development` (Vite), `build` (`npm ci --legacy-peer-deps` + `npm run build`, `ARG VITE_API_URL`), `production` (`nginx:alpine` serving `/dist` via envsubst template, dynamic `PORT`).

### 6.3 Nginx, monitoring, scripts

- **`nginx/beta.conf`:** HTTP→HTTPS redirect, Let's Encrypt ACME, TLS 1.2/1.3 + OCSP, security headers + CSP, gzip, `client_max_body_size 50M`; upstreams `api:8000` (keepalive 32) + `frontend:80`; rate-limit zones `api_limit` 10r/s + `login_limit` 5r/m (stricter on auth); WebSocket `/ws/` (86400s), SPA fallback. **`frontend/nginx.conf`:** in-image SPA (dynamic `${PORT}`, www→apex 301, hashed-asset long cache, no-cache HTML, per-location CSP, `/`→302 `/landing.html`, `/health`).
- **Monitoring:** `infrastructure/prometheus/` (prometheus.yml scraping api+worker `/metrics`, alerts.yml, alertmanager.yml), `infrastructure/grafana/` (provisioned datasource + `stratum-overview.json`). Sentry backend (`SENTRY_DSN`) + frontend (`VITE_SENTRY_DSN`).
- **Scripts:** deploy (`deploy-beta.sh`, `setup-railway.{sh,ps1}`, `smoke_test.sh`), DB (`init-db.sql`, `seed-data.sql`, `load_datasets.py`), ML (`train_models.py`, `build_ml_models.py`, `seed_owner` — renamed from `seed_superadmin`), codemods (`fix_*.py`).

### 6.4 CI/CD (GitHub Actions is the real pipeline; CircleCI is a no-op placeholder)

`.github/workflows/`:
- **`ci.yml`** — jobs: **backend-quality** (Ruff/Black/isort/mypy), **backend-tests** (unit+integration on pgvector+redis, "vacuous-pass" floor guard — set from first-milestone actuals and ratchet upward; the original's ≥3000 unit / ≥600 integration is the eventual reference bar — combined coverage ratchet, Codecov), **backend-security** (Bandit, pip-audit), **frontend** (npm audit, lint, `tsc --noEmit`, vitest coverage, build), **e2e** (Playwright/chromium, PR-only), **security** (Trivy fs+image SARIF), **secrets** (gitleaks), **gate** (release gate requiring all), **load-tests** (k6 smoke on main push). Python 3.11 / Node 20. **Add a residue gate:** `git grep -iE 'tenant_id|X-Tenant-ID|stripe' -- ':!*.md'` must return empty.
- **`docker.yml`** — build+push backend+frontend to GHCR (buildx, gha cache, semver+sha tags); `compose-test` health-checks the stack on PRs.
- **`pages.yml`** — deploy `backend/docs/**` to GitHub Pages.

### 6.5 Makefile targets (root delegates to `backend/Makefile`)

`help`, `dev` (uvicorn reload), `test` (unit), `test-all`, `test-cov`, `lint` (ruff+mypy), `format` (ruff --fix + black + isort), `migrate` (alembic upgrade head), `migration msg="..."`, `check` (lint+test), `clean`.

### 6.6 Deployment surfaces

- **Railway (primary):** `backend/railway.toml` + `railway.worker.toml` + `railway.beat.toml` + `frontend/railway.toml` (Dockerfile builder, `noCache`, healthchecks `/health/ready` + `/health`, `ON_FAILURE` restart w/ 3 retries). `scripts/setup-railway.*` bootstrap.
- **Vercel:** `vercel.json` — Vite build, SPA rewrites (~45 in original; regenerate for the final route set) → `/index.html`, global security headers (HSTS 2y preload, X-Frame-Options DENY, strict CSP allowing self + Sentry + Google Fonts + the API origin incl. wss).

*(Editions build system removed — ledger A.)*

---

## 7. Environment variables (names only — never commit secrets)

Required in non-dev: `SECRET_KEY`, `JWT_SECRET_KEY`, `PII_ENCRYPTION_KEY`, plus per-platform OAuth creds + SendGrid. *(`LICENSE_SIGNING_SECRET` and all `STRIPE_*` removed — ledger A.)* Groups:

- **Application:** `APP_NAME`, `APP_ENV`, `DEBUG`, `SECRET_KEY`, `API_V1_PREFIX`, `DOCS_API_KEY`, `METRICS_API_KEY`, `ENABLE_METRICS`.
- **Database:** `POSTGRES_USER/PASSWORD/DB/HOST/PORT`, `DATABASE_URL`, `DATABASE_URL_SYNC`, `DB_POOL_SIZE/MAX_OVERFLOW/POOL_RECYCLE/POOL_TIMEOUT`.
- **Redis/Celery:** `REDIS_HOST/PORT/PASSWORD`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`.
- **ML:** `ML_PROVIDER`, `ML_MODELS_PATH`, `ML_AUTO_TRAIN`, `GOOGLE_CLOUD_PROJECT`, `VERTEX_AI_ENDPOINT`, `GOOGLE_APPLICATION_CREDENTIALS`.
- **Ad platforms:** `USE_MOCK_AD_DATA`; Meta `META_APP_ID/APP_SECRET/ACCESS_TOKEN/API_VERSION/AD_ACCOUNT_IDS`; Google Ads `GOOGLE_ADS_DEVELOPER_TOKEN/CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN/CUSTOMER_ID`; TikTok `TIKTOK_APP_ID/SECRET/ACCESS_TOKEN/ADVERTISER_ID`; Snapchat `SNAPCHAT_CLIENT_ID/CLIENT_SECRET/ACCESS_TOKEN/AD_ACCOUNT_ID`. *(No PIXEL_ID/CAPI_TOKEN vars — CAPI senders are constructed in code, not from env.)*
- **WhatsApp:** `WHATSAPP_PHONE_NUMBER_ID/ACCESS_TOKEN/BUSINESS_ACCOUNT_ID/VERIFY_TOKEN/APP_SECRET/API_VERSION`. *(No ENABLE_WHATSAPP kill-switch — WhatsApp features activate when credentials are configured.)*
- **CRM:** `HUBSPOT_CLIENT_ID/CLIENT_SECRET/API_KEY`, `PIPEDRIVE_CLIENT_ID/CLIENT_SECRET`.
- **Market intel:** `MARKET_INTEL_PROVIDER`, `SERPAPI_KEY`, `DATAFORSEO_LOGIN/PASSWORD`.
- **Security:** `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `PII_ENCRYPTION_KEY`, `ENABLE_PUBLIC_SIGNUP`.
- **CORS:** `CORS_ORIGINS`, `CORS_ALLOW_CREDENTIALS`.
- **Observability:** `LOG_LEVEL`, `LOG_FORMAT`, `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_PROFILES_SAMPLE_RATE`, `SENTRY_RELEASE`, `ALERT_WEBHOOK_URL`.
- **Email/SMTP:** `SMTP_HOST/PORT/USER/PASSWORD/TLS/SSL`, `SENDGRID_API_KEY`, `SENDGRID_WEBHOOK_TOKEN`, `EMAIL_FROM_NAME/ADDRESS`, `FRONTEND_URL`, `OAUTH_REDIRECT_BASE_URL`, `EMAIL_VERIFICATION_EXPIRE_HOURS`, `PASSWORD_RESET_EXPIRE_HOURS`.
- **LLM/Copilot (opt-in):** `COPILOT_LLM_ENABLED`, `ANTHROPIC_API_KEY`, `COPILOT_LLM_MODEL`, `COPILOT_LLM_MAX_TOKENS`, `COPILOT_LLM_TIMEOUT_SECONDS`; RAG: `COPILOT_RAG_ENABLED`, `OPENAI_API_KEY`, `COPILOT_RAG_EMBEDDING_MODEL`, `COPILOT_RAG_TOP_K`, `COPILOT_RAG_CHUNK_CHARS`.
- **Asset storage:** `ASSET_STORAGE_BACKEND`, `ASSET_UPLOAD_DIR`, `ASSET_S3_BUCKET/ENDPOINT_URL/REGION/ACCESS_KEY/SECRET_KEY/PUBLIC_BASE_URL`.
- **Rate limiting:** `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_BURST`.
- **Feature flags:** `FEATURE_COMPETITOR_INTEL` (off), `FEATURE_WHAT_IF_SIMULATOR` (on), `FEATURE_AUTOMATION_RULES` (off), `FEATURE_GDPR_COMPLIANCE` (on), `FEATURE_KNOWLEDGE_GRAPH` (off), `ENABLE_CAMPAIGN_BUILDER_BEAT` (off), `ENABLE_NEWSLETTER_BEAT` (off), `FEATURE_DRIP_CAMPAIGNS` (off), `ENABLE_CAMPAIGN_PUBLISH` (off).
- **Frontend (Vite):** `VITE_API_URL` (includes `/api/v1`; the only API-URL name the code reads), `VITE_WS_URL` (includes `/ws`), `VITE_SENTRY_DSN`, `VITE_SENTRY_DEBUG`, `VITE_ENABLE_DEMO_MODE`.
- **Flower:** `FLOWER_USER`, `FLOWER_PASSWORD`.

---

## 8. Engineering conventions (enforce throughout)

- Type hints REQUIRED on all functions; Pydantic models for all API I/O; async/await for all I/O; docstrings on public functions; **coverage is governed by the CI ratchet** — `.coveragerc` `fail_under` applies to the COMBINED unit+integration run and may only ever be raised (74.0 at v2.1 revision time); treat 90%+ on `core/`, `autopilot/`, `analytics/` as the long-term target the ratchet climbs toward, not a merge gate.
- Use `datetime.now(timezone.utc)` (never `utcnow()`); `secrets` module (never `random`) for security tokens; `hmac.compare_digest()` for constant-time comparisons; **Fernet-encrypt PII before storage**; structured logging via structlog (JSON).
- **Do NOT:** skip trust-gate checks; hardcode thresholds (use `Organization` settings); execute automations without audit logging; put PII in JWT claims; store plaintext credentials in frontend; commit `.env`/API creds; use `random` for tokens; **reintroduce `tenant_id`, tenant headers, Stripe, or tier gating** — if multi-tenancy or billing is ever needed, it is a separate migration project.
- Frontend: use semantic Tailwind tokens (`bg-card`, `text-foreground`, `border-border`, `text-primary`) over hex; `text-muted-foreground` not `text-gray-*`; compose primitives before bespoke surfaces; glow only for the primary KPI; mono for labels/status, Geist for body/display.
- **Git:** branch `feature/STRAT-123-description`; conventional commits `feat|fix|refactor|test|docs(scope): message [STRAT-123]`; never merge without passing CI.

---

## 9. Build sequencing (milestones)

Build in dependency order so each layer is testable before the next:

1. **Foundation** — repo scaffold, Docker Compose (db/redis/api), config (`core/config.py` with prod fail-closed validators), `db/session.py`, base mixins (Timestamp/SoftDelete), `base_models.py` incl. `Organization` singleton, migration 001. Health endpoints.
2. **Auth** — JWT + refresh + Redis blacklist, bcrypt, RBAC permissions (owner→viewer), MFA (TOTP), API keys, audit pipeline. Full auth integration tests (login/register[flag]/refresh/logout/mfa/otp/reset/invite/verify).
3. **Middleware stack** — CORS/timing/security/audit/ratelimit/gzip/exception in documented order; SSRF guard; CSRF.
4. **Trust engine core** — signal_health scoring, EMQ calculation, trust_gate + org config, autopilot service + enforcer, fact tables (trust_layer). Cover these modules as close to 90% as practical — the enforced bar is the CI coverage ratchet (only ever raise it).
5. **Domain features** (parallelizable) — campaigns/builder, Brands (client module), CDP (profiles/segments/identity/funnels), attribution (MTA + Markov + Shapley), pacing, profit/ROAS, reporting, CRM, CAPI/EMQ, audience sync, autopilot enforcement. Each: model → migration → service → endpoints → schemas → tests.
6. **ML** — predictors/forecaster/optimizer/segmenter/explainability; build-time pre-training; retraining pipeline.
7. **Integrations** — OAuth (4 platforms), sync orchestrator, platform adapters + registry, WhatsApp, Slack, SendGrid. *(No Stripe — ledger A.)*
8. **Workers** — Celery app + beat schedule + all task submodules + `app/tasks/` rollups.
9. **Frontend foundation** — Vite + theme system (tokens, ThemeProvider, pre-paint script), primitive library (Card/KPI/StatusPill/Chart/DataTable/ConfirmDrawer/InsightsPanel/nav) each with vitest, axios client (refresh mutex), stores + contexts, i18n (en/ar + RTL).
10. **Frontend shells & views** — DashboardLayout, ConsoleLayout, CMSLayout, PortalLayout; all views lazy-loaded; React Query hooks; onboarding wizard; public marketing site (incl. `/ar`).
11. **Ops** — Nginx, Prometheus/Grafana, Sentry, GitHub Actions CI (all jobs + gate + residue gate), Railway/Vercel configs.
12. **Hardening** — the security pass: MFA-at-login, audit-pipeline key alignment, API-key authenticator, secrets-at-rest, webhook signature verification, Brand-assignment access audit, signup-flag audit.

---

## 10. Acceptance criteria / validation checklist

- [ ] **Build:** `make check` (backend lint + mypy + tests) green; `npm run build` (`tsc --noEmit` + vite) green; `docker compose up -d` brings up all 7 services healthy; `/health/ready` returns 200 only after DB + Redis are up.
- [ ] **Auth flow:** invite (or flag-gated signup) → email verify → login → MFA challenge/exchange → access+refresh issued (no PII in claims) → refresh rotation + blacklist on logout → login lockout after N failures → idle timeout.
- [ ] **Access control:** Brand-scoped users cannot read/write outside assigned Brands; viewer/portal users are read-only; owner bypass works; raw-SQL/global-list/debug endpoints are owner-only (403 otherwise).
- [ ] **No removed-scope residue:** CI grep gate for `tenant_id`, `X-Tenant-ID`, `stripe`, and `{tenant` key-builder patterns (excluding docs/changelog) returns empty.
- [ ] **Global uniqueness (§4.9 table):** every converted constraint has positive + negative tests — duplicate email/API-key-hash/slug/external-id is rejected globally with the documented 409/422 contract; each carries the `# was tenant-scoped; now global` comment.
- [ ] **De-namespaced keys:** Redis cache/rate-limit keys, Celery routing, SSE channels, and asset paths contain no tenant segment; a cache round-trip test proves reads hit writes.
- [ ] **Trust gate:** autopilot never auto-executes when signal_health < 70; enforcement modes (Advisory/Soft/Hard) behave per spec; every automation writes an audit log; thresholds read from `Organization` settings, never constants.
- [ ] **Data integrity:** all migrations apply cleanly up and down; pgvector migration works; PII key loads at startup; rotation runbook exists.
- [ ] **API contract:** OpenAPI docs gated by `DOCS_API_KEY` in prod; every mutating endpoint has auth + schema + audit + rate limit; feature-flagged routers return 404/403 (per flag semantics) when off — knowledge graph returns 503 (not crash) without Apache AGE.
- [ ] **Frontend:** theme switches with no flash (light/dark/system); RTL renders for `/ar` and in-app Arabic; 401 triggers single mutex-guarded refresh; primitives pass ARIA/keyboard vitests; Playwright specs pass across 5 browser projects.
- [ ] **Coverage:** combined unit+integration coverage meets the `.coveragerc` ratchet (`fail_under`, only ever raised; 74.0 at v2.1 revision time), with `core/`, `autopilot/`, `analytics/` trending toward the 90% long-term target; CI vacuous-pass floor guard satisfied at its ratcheted level.
- [ ] **Ops:** Prometheus scrapes `/metrics` (bearer-gated); Sentry receives backend + frontend errors; GHCR images build; Railway health probes pass; `.beta.yml` stack passes `smoke_test.sh` on DigitalOcean.

---

## 11. Notable behaviors to reproduce faithfully (easy to miss)

- Authorization is **role + Brand assignment** — there is no data-partition (tenant) dimension. `owner` inherits all former superadmin semantics including scoping bypass and exclusive access to debug/raw-SQL endpoints.
- Token middleware **fails open if Redis is down** (blacklist unavailable) but still rejects non-`access` token types.
- Several features ship **gated OFF** by default: competitor intel, automation rules, knowledge graph (needs Apache AGE — returns 503, not crash), drip execution, campaign publish, newsletter/campaign-builder beats, public signup.
- **Off-flag status-code convention:** org-level FeatureGate'd routes return **404** when the feature flag is off (the route "doesn't exist" for that deployment); environment-gated capabilities (missing infra/credentials, e.g. knowledge graph without Apache AGE, WhatsApp OTP without credentials) return **503** (the feature exists but its backing service is unavailable). Reproduce both semantics faithfully.
- Copilot default is a **deterministic keyword classifier**; Anthropic Claude generation + OpenAI-embedding pgvector RAG are opt-in paths.
- Tokens stored in **sessionStorage** (not localStorage) with in-memory caching + refresh mutex; selected Brand id in localStorage.
- ML models **pre-trained at Docker build time** to avoid multi-GB runtime training.
- The `uk` (Ukrainian) locale file exists but is **not wired** into i18n — reproduce as a deliberate dormant asset.
- The frontend previously had three near-duplicate authenticated shells; only the tenant twin is gone — **dashboard and console remain distinct shells**, do not merge them.

---

## 12. OPTIONAL track — converting a live multi-tenant database

> **Default path is greenfield (fresh Alembic chain, §4.8).** Use this section only if collapsing an existing multi-tenant deployment into this single-client system. If that is your situation, this section becomes a hard prerequisite to Milestone 1 — do not run schema migrations against production data without completing it.

1. **Freeze & snapshot:** maintenance window; disable Celery beat + workers; take a verified DB snapshot (`pg_dump` + point-in-time marker). This snapshot is the rollback contract for the entire conversion.
2. **Select the surviving tenant:** record its `tenant_id`. Export a manifest of all other tenants (row counts per table) for the archive audit.
3. **Archive-then-delete:** per business table, `pg_dump --table` filtered exports of non-surviving tenants to cold storage (encrypted, retention per GDPR/compliance settings) → then delete those rows in FK-safe order. Verify counts match the manifest.
4. **PII re-keying:** decrypt every `EncryptedString` column with the surviving tenant's key from `tenant_encryption_keys`, re-encrypt with the new global `PII_ENCRYPTION_KEY`, in batched transactions with a progress checkpoint table. Only then drop `tenant_encryption_keys`.
5. **Uniqueness pre-flight:** before applying `UNIQUE(x)` constraints (§4.9), run duplicate-detection queries per constraint; resolve collisions explicitly (they can only come from residue or historical soft-deleted rows).
6. **Schema collapse migrations (reversible):** drop `tenant_id` columns/FKs/indexes, rebuild composite indexes without the tenant prefix, convert unique constraints, collapse `TenantEnforcementSettings` → global singleton, migrate `Tenant` row → `Organization` singleton. Every migration ships a working `downgrade()` or a documented snapshot-restore rollback.
7. **Key-space flush:** flush Redis (cache/broker/result DBs) — old tenant-prefixed keys are garbage post-conversion; re-enqueue beat from a clean schedule.
8. **Cutover validation:** run the full §10 checklist plus: row counts match surviving-tenant manifest; a sample of re-keyed PII decrypts correctly; auth works for surviving-tenant users only; `/health/ready` green; smoke Playwright pass.
9. **Rollback drill:** before the real run, execute steps 1–8 against a staging restore of production and time it; the maintenance window is 2× the drill (+25% buffer).

---

## 13. Runner configuration — Claude Code permission mode (read before executing this prompt)

> ⚠️ **The mode must be set by the launcher, not by this document.** Claude Code sets permission modes via CLI flag, Shift+Tab, or settings — never via prompt text. `defaultMode: "auto"` is honored only in user settings (`~/.claude/settings.json`), not project settings, and Claude Code on the web ignores `bypassPermissions`/`dontAsk` from checked-in settings. Configure one of the following BEFORE pasting this prompt.

### 13.1 Recommended per environment

| Environment | Mode | Launch |
|---|---|---|
| Dev laptop (real machine) — **default recommendation** | `acceptEdits` + §13.2 allowlist | `claude --permission-mode acceptEdits` |
| Long unattended build, account eligible (Sonnet 4.6 / Opus 4.6 on Anthropic API; admin-enabled on Team/Enterprise) | `auto` (classifier-reviewed) | set `{"permissions":{"defaultMode":"auto"}}` in `~/.claude/settings.json`, or select Auto via Shift+Tab |
| Isolated container / ephemeral CI only (no secrets, disposable) | `bypassPermissions` | `claude --dangerously-skip-permissions` (refuses to run as root/sudo) |
| Headless CI with fixed tool surface | `dontAsk` + explicit allow rules | `claude --permission-mode dontAsk` |

Never use `bypassPermissions` on a developer machine or anywhere with real credentials. In `auto` headless (`-p`) runs, repeated classifier blocks abort the session — keep the §13.2 allowlist in place so routine commands never reach the classifier.

### 13.2 Project allowlist (commit as `.claude/settings.json`)

Pre-approves this build's routine commands so `acceptEdits` sessions run without stalls while everything else still prompts:

```json
// .claude/settings.json  — data-test: n/a (config file)
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Bash(make *)",
      "Bash(npm run *)", "Bash(npm ci)", "Bash(npm install *)",
      "Bash(npx vitest *)", "Bash(npx playwright *)", "Bash(npx tsc *)",
      "Bash(pytest *)", "Bash(ruff *)", "Bash(black *)", "Bash(isort *)", "Bash(mypy *)",
      "Bash(alembic *)",
      "Bash(docker compose *)", "Bash(docker build *)",
      "Bash(git status)", "Bash(git diff *)", "Bash(git add *)", "Bash(git commit *)", "Bash(git checkout -b *)",
      "Bash(pip install *)", "Bash(python scripts/*)"
    ],
    "deny": [
      "Read(**/.env)", "Read(**/.env.*)",
      "Bash(git push --force*)",
      "Bash(rm -rf /*)"
    ]
  }
}
```

Notes: deny rules win over allow rules in every mode including bypass; protected paths (`.git`, `.claude`, shell rc files) are never auto-approved outside bypass; allow rules have no effect in bypass (everything is already approved). `git push` and deploy commands stay human-approved by default; the one sanctioned exception is `Bash(git push origin main)` on a dedicated single-purpose deployment repo whose remote the owner has explicitly authorized (Railway auto-deploy flow) — force-push stays denied everywhere.

### 13.4 If running on Claude Fable 5 (CLI)

- **Use `acceptEdits` + the §13.2 allowlist:** `claude --model fable --permission-mode acceptEdits`. Fable 5 self-verifies and sustains long sessions, so review happens at milestone `git diff` boundaries, not per-edit.
- **Auto mode:** only if "Auto" actually appears in your Shift+Tab mode indicator (that visibility IS the eligibility check — Anthropic API only, admin-enabled on Team/Enterprise). Prefer attended over headless: repeated classifier blocks abort headless auto sessions, and Fable 5 carries its own classifiers that can auto-fallback the model to Opus 4.8 (return with `/model fable`). The security-hardening milestone (§9.12) is the likeliest to brush a classifier.
- **Cost discipline:** Fable 5 ≈ 2× Opus 4.8 per token — run one §9 milestone per session, state the milestone's §10 acceptance criteria as the goal, skip step-by-step micromanagement and verification reminders.
- **Version:** Claude Code v2.1.170+ required for Fable 5 (`claude update`).

### 13.5 Session hygiene

1. Verify the mode indicator before starting (Shift+Tab cycles default → acceptEdits → plan; auto/bypass appear only when enabled).
2. Run each §9 milestone as its own session/branch; review `git diff` at milestone boundaries — that's the review point `acceptEdits` trades for speed.
3. If a session stalls on a repeated prompt, add the specific pattern via `/permissions` rather than escalating the whole mode.

---

*End of build prompt (v2.1). Treat every "match the contract" as a hard acceptance criterion. Do not add scope beyond what is specified here — and do not remove anything not listed in the §0.1 removal ledger.*

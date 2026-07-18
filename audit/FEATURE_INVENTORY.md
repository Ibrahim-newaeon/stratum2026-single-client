# PHASE 1 — FEATURE INVENTORY (master checklist)
Audit date: 2026-07-18. Sources: `backend/app/api/v1/__init__.py` router registry (63 include_router calls), `backend/app/main.py` app-level mounts, `backend/app/workers/celery_app.py` (+ task modules), `frontend/src/App.tsx` route table (lines 274–1732), `frontend/src/components/primitives/nav/{dashboardNav,consoleNav}.ts`, `backend/app/features/flags.py`, `backend/app/core/feature_gate.py`, README.md feature map, CLAUDE.md.

Granularity: one FEAT per user-facing feature/subsystem (not per endpoint). 100% of registered routers, beat entries, task modules, and frontend surfaces are covered below; the final health matrix must account for every ID.

## A. Authentication & Session
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-001 | Login/logout, JWT access+refresh rotation, token blacklist | `endpoints/auth.py` (reg `v1/__init__.py:80`) |
| FEAT-002 | Signup (invite-only; `ENABLE_PUBLIC_SIGNUP` gate) | `endpoints/auth.py`, `core/config.py:252` |
| FEAT-003 | Password reset + email verification (email-links) | `endpoints/auth.py`; FE `/forgot-password`, `/verify-email` (App.tsx:316,336) |
| FEAT-004 | MFA (TOTP) challenge-exchange at login | `endpoints/mfa.py:347`, `services/mfa_service.py` |
| FEAT-005 | RBAC role hierarchy (owner>admin>manager>analyst>viewer) + portal `user_type` + `cms_role` | `ProtectedRoute.tsx:21,30`, backend role deps |
| FEAT-006 | API key management + X-API-Key programmatic auth | `endpoints/api_keys.py` (require_owner), `endpoints/programmatic.py` |
| FEAT-007 | AuthContextMiddleware (request auth context; replaced TenantMiddleware) | `middleware/auth_context.py`, `main.py:391` |
| FEAT-008 | CSRF protection middleware | `middleware/csrf.py`, `main.py:388` |
| FEAT-009 | Team management + invitations (accept-invite flow) | FE `/accept-invite` (App.tsx:348), `/dashboard/team` (App.tsx:1453), `endpoints/users.py` |
| FEAT-010 | User profile/account management | `endpoints/users.py` (reg :87) |

## B. Core Domain APIs (v1 routers)
| ID | Feature | Primary evidence (registry line) |
|---|---|---|
| FEAT-020 | Campaigns CRUD + detail | `endpoints/campaigns.py` (:94) |
| FEAT-021 | Digital assets / DAM | `endpoints/assets.py` (:101) |
| FEAT-022 | Automation rules engine | `endpoints/rules.py` (:108; env-gated `feature_automation_rules`) |
| FEAT-023 | Competitor intelligence | `endpoints/competitors.py` (:115; env-gated `feature_competitor_intel`) |
| FEAT-024 | What-if ML simulator | `endpoints/simulator.py` (:122; FeatureGate WHAT_IF_SIMULATOR) |
| FEAT-025 | Core analytics/KPIs | `endpoints/analytics.py` (:130) |
| FEAT-026 | AI analytics (scaling, fatigue, anomalies) | `endpoints/analytics_ai.py` (:204) |
| FEAT-027 | GDPR export/erasure/consent | `endpoints/gdpr.py` (:137; FeatureGate GDPR_TOOLS) |
| FEAT-028 | WhatsApp Business messaging + inbound webhook | `endpoints/whatsapp.py` router (:145) + webhook_router (:152) |
| FEAT-029 | ML training / model registry (owner) | `endpoints/ml_training.py` (:164) |
| FEAT-030 | Live predictions / ROAS optimization | `endpoints/predictions.py` (:172) |
| FEAT-031 | Conversions API (CAPI) | `endpoints/capi.py` (:179) |
| FEAT-032 | Meta CAPI QA/event collection | `endpoints/meta_capi.py` (:186) |
| FEAT-033 | Landing CMS (multi-language) | `endpoints/landing_cms.py` (:192) |
| FEAT-034 | EMQ one-click QA fixes | `endpoints/qa_fixes.py` (:198) |
| FEAT-035 | Owner console (platform admin) | `endpoints/console.py` (:211) |
| FEAT-036 | Launch-readiness wizard | `endpoints/launch_readiness.py` (:218) |
| FEAT-037 | Dashboard overview/signal health/settings | `endpoints/dashboard.py` (:226) |
| FEAT-038 | Owner platform analytics | `endpoints/console_analytics.py` (:233; ⚠ stacked prefix `/console/analytics/console`) |
| FEAT-039 | Autopilot (trust-gated actions) | `endpoints/autopilot.py` (:243) |
| FEAT-040 | Autopilot enforcement (budget/ROAS restrictions) | `endpoints/autopilot_enforcement.py` (:251) |
| FEAT-041 | Campaign builder (multi-platform wizard) | `endpoints/campaign_builder.py` (:257) |
| FEAT-042 | Feature flags API (org + owner console) | `endpoints/feature_flags.py` (:267) |
| FEAT-043 | AI insights/recommendations | `endpoints/insights.py` (:273) |
| FEAT-044 | Trust layer / signal health API | `endpoints/trust_layer.py` (:280) |
| FEAT-045 | EMQ v2 | `endpoints/emq_v2.py` (:287) |
| FEAT-046 | Integrations hub (CRM etc.) | `endpoints/integrations.py` (:293) |
| FEAT-047 | Pacing & forecasting | `endpoints/pacing.py` (:299) |
| FEAT-048 | Profit ROAS / COGS | `endpoints/profit.py` (:306) |
| FEAT-049 | Multi-touch attribution | `endpoints/attribution.py` (:313) |
| FEAT-050 | Data-driven attribution (Markov/Shapley) | `endpoints/data_driven_attribution.py` (:319) |
| FEAT-051 | Automated reporting (PDF/Slack/email, schedules) | `endpoints/reporting.py` (:325) |
| FEAT-052 | Audit services (EMQ measure, offline conv, AB, LTV) | `endpoints/audit_services.py` (:332; ⚠ stacked prefix `/audit/audit-services`) |
| FEAT-053 | Newsletter & email campaigns | `endpoints/newsletter.py` (:340) |
| FEAT-054 | Onboarding wizard API | `endpoints/onboarding.py` (:354) |
| FEAT-055 | Ad-platform OAuth flows | `endpoints/oauth.py` (:361) |
| FEAT-056 | Platform OAuth-app credential mgmt | `endpoints/platform_credentials.py` (:368) |
| FEAT-057 | In-app notifications API | `endpoints/notifications.py` (:375) |
| FEAT-058 | Programmatic public API (X-API-Key) | `endpoints/programmatic.py` (:389) |
| FEAT-059 | CDP (profiles/segments/events/identity/consent) | `endpoints/cdp.py` (:396) |
| FEAT-060 | Product changelog API | `endpoints/changelog.py` (:403) |
| FEAT-061 | Client account management | `endpoints/clients.py` (:409) |
| FEAT-062 | CMS (blog/pages/contacts) | `endpoints/cms.py` (:421) |
| FEAT-063 | Knowledge graph | `endpoints/knowledge_graph.py` (:427; env-gated, shelved) |
| FEAT-064 | Inbound webhook processing (owner) | `endpoints/webhooks.py` (:435) |
| FEAT-065 | Slack integration API | `endpoints/slack.py` (:442) |
| FEAT-066 | AI onboarding agent | `endpoints/onboarding_agent.py` (:449) |
| FEAT-067 | Embed widgets (authed mgmt; ⚠ public_router `/embed/v1` NOT registered) | `endpoints/embed_widgets.py` (:456) |
| FEAT-068 | CDP audience sync → ad platforms | `endpoints/audience_sync.py` (:463) |
| FEAT-069 | AI copilot chat (RAG over docs) | `endpoints/copilot.py` (:470) |
| FEAT-070 | AI intelligence | `endpoints/intelligence.py` (:476; ⚠ stacked prefix `/intelligence/analytics/insights`) |
| FEAT-071 | Advanced analytics | `endpoints/advanced_analytics.py` (:485) |
| FEAT-072 | Enterprise compliance | `endpoints/compliance.py` (:491; ⚠ stacked prefix `/compliance/admin/compliance`) |
| FEAT-073 | Outbound integrations (webhooks out) | `endpoints/outbound_integrations.py` (:501) |
| FEAT-074 | Developer portal | `endpoints/developer.py` (:509) |
| FEAT-075 | SendGrid inbound email webhook | `endpoints/sendgrid_webhook.py` (:515) |
| FEAT-076 | Drip campaigns | `endpoints/drip_campaigns.py` (:522) |
| FEAT-077 | Web push notifications (VAPID) | `endpoints/push_notifications.py` (:529) |
| FEAT-078 | Memory debug router (⚠ defined, NOT registered) | `endpoints/memory_debug.py` |

## C. App-level HTTP surface (outside v1 router)
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-085 | Health endpoints (`/health`, `/health/ready`, `/health/live`) | `main.py:571,606,624` |
| FEAT-086 | Prometheus `/metrics` | `main.py:764` |
| FEAT-087 | Public demo metrics + public SSE stream | `main.py:632,723` |
| FEAT-088 | Authed SSE real-time stream `/api/v1/events/stream` | `main.py:781` |
| FEAT-089 | WebSocket `/ws` (real-time dashboard) + `/ws/stats` | `main.py:836,919` |
| FEAT-090 | API docs (`/docs`, `/redoc`, `/openapi.json`, API-key gated in protected envs) | `main.py:335–354` |
| FEAT-091 | SPA/static serving (uploads/assets/images/icons + catch-all) | `main.py:521–548` |

## D. Background Jobs (Celery `stratum_ai` app)
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-100 | Campaign data sync (hourly beat + on-demand) | `workers/tasks/sync.py:45,188`; beat `sync-all-campaigns` |
| FEAT-101 | Daily forecasts (06:00) + on-demand forecast | `workers/tasks/forecast.py` |
| FEAT-102 | Creative fatigue scores (03:00) | `workers/tasks/creative.py:23` |
| FEAT-103 | Audit-log queue processor (every min) | `workers/tasks/audit.py:26` |
| FEAT-104 | Pipeline health check (hourly) + worker heartbeat (every min) | `workers/tasks/monitoring.py:69,113` |
| FEAT-105 | Daily scores calc (04:00) | `workers/tasks/scores.py:25` |
| FEAT-106 | Prediction runs (*/30) + ROAS alerts | `workers/tasks/ml.py` |
| FEAT-107 | Scheduled WhatsApp sends (every min) + broadcast | `workers/tasks/whatsapp.py` |
| FEAT-108 | Autopilot apply-actions queue (*/5) + single-apply + rollback | `tasks/apply_actions_queue.py:1336–1796` |
| FEAT-109 | Signal-health daily rollup (02:00) → FactSignalHealthDaily | `tasks/signal_health_rollup.py` |
| FEAT-110 | Attribution-variance daily rollup (02:15) | `tasks/attribution_variance_rollup.py` |
| FEAT-111 | Audience auto-sync sweep (*/15) | `tasks/audience_auto_sync.py` |
| FEAT-112 | Campaign-builder connector beat trio (gated `ENABLE_CAMPAIGN_BUILDER_BEAT`): ad-account sync, token refresh, health check | `workers/campaign_builder_tasks.py`; celery_app.py:200 |
| FEAT-113 | Newsletter scheduled sends (gated `ENABLE_NEWSLETTER_BEAT`) + send task | `workers/newsletter_tasks.py`; celery_app.py:225 |
| FEAT-114 | Rules evaluation beat (gated `FEATURE_AUTOMATION_RULES`) | `workers/tasks/rules.py:111`; celery_app.py:237 |
| FEAT-115 | Competitor data refresh beat (gated `FEATURE_COMPETITOR_INTEL`; ⚠ fabricates data via random) | `workers/tasks/competitors.py:91`; celery_app.py:244–248 |
| FEAT-116 | CDP compute tasks (segment ✓, funnel ✓; ⚠ all-segments/RFM/traits/all-funnels ORPHANED) | `workers/tasks/cdp.py:34–453` |
| FEAT-117 | CMS publish tasks (publish_cms_post ✓; ⚠ scheduled-posts + versioning ORPHANED) | `workers/tasks/cms.py` |
| FEAT-118 | Dead-letter queue sink + task-failure hook | `workers/celery_app.py:269,314` |
| FEAT-119 | CRM sync tasks (HubSpot/Zoho sync + writeback; ⚠ module NOT in `include`, `.delay` sites exist, own un-merged beat) | `workers/crm_sync_tasks.py` |
| FEAT-120 | Legacy standalone Celery app `data_sync.py` (11 tasks + own beat) | `workers/data_sync.py:96,114` |
| FEAT-121 | Legacy standalone Celery app `automation_runner.py` (7 tasks + own beat) | `workers/automation_runner.py:95` |
| FEAT-122 | ML retraining pipeline (factory-registered `ml.retrain_models`) | `ml/retraining_pipeline.py:636` |
| FEAT-123 | Celery task routing to queues (sync/rules/intel/ml) | `celery_app.py:80` (⚠ route keys don't match registered names) |

## E. Files & Storage
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-130 | File storage service (S3 via boto3 / local `uploads/`) | `services/storage.py` |
| FEAT-131 | Asset upload + `/uploads/assets` static serving | `endpoints/assets.py`, `main.py:521` |
| FEAT-132 | Report artifact generation/delivery (PDF) | `services/reporting/delivery.py` |

## F. Caching & Rate Limiting
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-135 | Redis cache (async client) | `redis[asyncio]` in requirements; `core/` usage TBD Phase 7 |
| FEAT-136 | Rate limiting middleware | `middleware/rate_limit.py` |

## G. Realtime
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-140 | WebSocket manager + `/ws` (token-authed) | `main.py:836`, `core/` websocket module |
| FEAT-141 | SSE streams (public + authed) | `main.py:723,781` |
| FEAT-142 | Frontend `useWebSocket` hooks (⚠ exported, used by NO component) | `frontend/src/hooks/useWebSocket.ts` |

## H. Notifications & Email
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-145 | Email service (transactional; Resend/SendGrid) | `services/email_service.py` |
| FEAT-146 | In-app notification center | `endpoints/notifications.py`, `services/notifications/` |
| FEAT-147 | Web push (VAPID) | `endpoints/push_notifications.py` |
| FEAT-148 | Slack notifications | `endpoints/slack.py`, reporting delivery |
| FEAT-149 | WhatsApp customer messaging | `services/whatsapp_service.py` |

## I. Billing
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-155 | Billing/licensing/Stripe — **REMOVED by design** in STRAT-SC-001 (`5e9ac004`, `4a68bf4a`); CI residue-gates stripe. ⚠ Dead `Billing` nav item remains (`dashboardNav.ts:526`, documented known gap) | conversion commits; `figma-theme.md` known-gap note |

## J. Integrations
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-160 | Meta OAuth + Marketing API connector | `services/oauth/`, README #9 |
| FEAT-161 | Google Ads OAuth + connector | `services/oauth/` |
| FEAT-162 | TikTok OAuth + connector | `services/oauth/` |
| FEAT-163 | Snapchat OAuth + connector | `services/oauth/` |
| FEAT-164 | CRM integrations (HubSpot, Zoho; Pipedrive/Salesforce per README) | `services/crm/`, `workers/crm_sync_tasks.py` |
| FEAT-165 | Outbound webhooks | `endpoints/outbound_integrations.py` |
| FEAT-166 | Inbound webhooks (WhatsApp/Meta HMAC, SendGrid URL-token, owner `/webhooks`) | FEAT-028/064/075 cross-ref |

## K. Config & Feature Flags
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-170 | Env kill-switch flags (5 `feature_*` + `ENABLE_*` gates) | `core/config.py:447–463`, `core/feature_gate.py:38–57` |
| FEAT-171 | Org-configurable flags (JSONB overrides on `DEFAULT_ORG_FEATURES`) | `features/flags.py:48–60`, `features/service.py` |
| FEAT-172 | Console flag management UI + API | `endpoints/feature_flags.py:99–179`, FE `/console/feature-flags` |
| FEAT-173 | Settings/config system (pydantic-settings, .env surface) | `core/config.py`; `.env.example` (70 keys) |

## L. Frontend Surfaces
| ID | Feature | Primary evidence (App.tsx) |
|---|---|---|
| FEAT-180 | Marketing site (~35 public routes: landing EN/AR, features, solutions, blog, docs, legal…) | :276–740 |
| FEAT-181 | Auth views (login/signup/forgot/reset/verify/accept-invite) | :296–348 |
| FEAT-182 | Operator dashboard shell + 3-group sidebar (~70 routes) | :822–1487; `dashboardNav.ts:214` |
| FEAT-183 | Owner console shell (19 routes) | :1504–1660; `consoleNav.ts:40` |
| FEAT-184 | CMS portal (12 routes, `cms_role` guard) | :370–479 |
| FEAT-185 | Client portal (`user_type=portal`) | :752–786 |
| FEAT-186 | Onboarding wizard + OAuth connect result | :797,810 |
| FEAT-187 | Route guards (ProtectedRoute/OnboardingGuard/CMSProtectedRoute) | `ProtectedRoute.tsx` |
| FEAT-188 | Legacy redirects (`/app/:tenantId/*`, `/dashboard/owner*`, superadmin, am/tenant) | :1495,1676–1707,1487 |
| FEAT-189 | Theme system (dark/light/system, Opal Hotel rebrand applied) | `theme/ThemeProvider.tsx` |
| FEAT-190 | Feature-flag store + gating hooks | `stores/featureFlagsStore.ts`, `api/featureFlags.ts` |
| FEAT-191 | Custom dashboard (react-grid-layout) | :865 |
| FEAT-192 | `superads-dashboard/` static mockup (⚠ dead reference code, not built/served) | repo root |

## M. Observability
| ID | Feature | Primary evidence |
|---|---|---|
| FEAT-200 | Structured logging (structlog JSON) + request logging middleware | `middleware/request_logging.py` |
| FEAT-201 | Audit middleware + audit-log pipeline | `middleware/audit.py`, `workers/tasks/audit.py` |
| FEAT-202 | Prometheus metrics + Grafana/monitoring compose | `main.py:764`, `monitoring/`, `docker-compose.monitoring.yml` |
| FEAT-203 | Sentry error tracking | glossary; config TBD Phase 12 |
| FEAT-204 | Flower (Celery monitoring) | compose service `flower` |
| FEAT-205 | CI (GitHub Actions incl. residue gate; CircleCI legacy?) | `.github/workflows/ci.yml`, `.circleci/config.yml` |

## Domain absence notes
- **Multi-tenancy features**: intentionally removed (STRAT-SC-001) — not inventoried as features; residue tracked in Phase 2.
- **Payments/Billing**: no live billing subsystem exists (FEAT-155 records the removal + dead nav residue).

## Phase-seeds discovered during inventory (to be dispositioned in later phases)
1. 4 stacked-prefix routers → Phase 5 (FEAT-038/052/070/072)
2. Unregistered routers: `memory_debug`, `embed_widgets.public_router` → Phase 5 (FEAT-078/067)
3. Celery `task_routes` name mismatch → Phase 6 (FEAT-123)
4. Orphaned tasks (CDP ×4, CMS ×2, publish_retry, CRM module ×7) → Phase 6 (FEAT-116/117/119)
5. Legacy standalone Celery apps `data_sync.py`/`automation_runner.py` → Phase 6 (FEAT-120/121)
6. `useWebSocket` unused by any component → Phase 8/11 (FEAT-142)
7. Dead Billing nav link → Phase 11 (FEAT-155)
8. Docs claim flag defaults `true`, code says `false` (`decisions-adr.md:344` vs `config.py:447,449`) → Phase 10
9. Docs claim "1 revision" migration chain (CLAUDE.md) but 3 exist → Phase 12 (stale doc)

**Inventory count: 124 features** (FEAT-001…FEAT-205, non-contiguous numbering by domain).

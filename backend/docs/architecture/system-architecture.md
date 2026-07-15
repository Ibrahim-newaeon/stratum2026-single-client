# Stratum AI — System Architecture Overview

> **Document Version:** 1.2.0  
> **Last Updated:** 2026-04-26  
> **Audience:** Engineers, DevOps, Technical PMs  
> **Scope:** Full-stack architecture from client to database
>
> **2026-07 update**: Stratum AI was converted to a **single-client
> deployment** (STRAT-SC-001) — the multi-tenancy model, subscription
> tiers, and Stripe billing described below (originally written for the
> multi-tenant SaaS architecture) were fully removed. One `Organization`
> row replaces the `tenants` table; there is no per-customer isolation
> layer. The "Multi-Tenancy Model" section is kept below as **historical
> reference only** and is annotated accordingly. See
> `docs/single-client-conversion.md` for the removal ledger and current
> architecture.

---

## Table of Contents

1. [Architecture Philosophy](#architecture-philosophy)
2. [High-Level Diagram](#high-level-diagram)
3. [Frontend Architecture](#frontend-architecture)
4. [Backend Architecture](#backend-architecture)
5. [Database Layer](#database-layer)
6. [Data Pipeline](#data-pipeline)
7. [Trust Engine](#trust-engine)
8. [Autopilot System](#autopilot-system)
9. [Multi-Tenancy Model](#multi-tenancy-model)
10. [Security Architecture](#security-architecture)
11. [Deployment Architecture](#deployment-architecture)
12. [Technology Stack](#technology-stack)

---

## Architecture Philosophy

Stratum AI follows three core architectural principles:

1. **Safety First**: No automation executes without passing the Trust Gate. The system prefers false negatives (missed opportunities) over false positives (bad automation).

2. **Platform Agnostic**: All platform-specific logic (Meta, Google, TikTok) is abstracted behind unified interfaces. The core system never speaks platform API directly.

3. **Single-Org, Role-Scoped**: One `Organization` per deployment. Access
   control is role-based (owner/admin/manager/analyst/viewer), not
   tenant-based — there is no cross-customer data to isolate.

---

## High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  React SPA  │  │  CMS Editor │  │ Landing     │  │ WhatsApp Web        │ │
│  │  (Vite)     │  │  (Tiptap)   │  │ (Static)    │  │ (Twilio/Web)        │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                │                    │            │
│         └────────────────┴────────────────┴────────────────────┘            │
│                                       │                                      │
│                              ┌────────▼────────┐                            │
│                              │   Nginx / CDN   │                            │
│                              │   (Vercel)      │                            │
│                              └────────┬────────┘                            │
└───────────────────────────────────────┼─────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┼─────────────────────────────────────┐
│                              API LAYER│                                      │
│                              ┌────────▼────────┐                            │
│                              │   FastAPI       │                            │
│                              │   (Python 3.11) │                            │
│                              │                 │                            │
│                              │  ┌───────────┐  │                            │
│                              │  │  Routers  │  │  v1/endpoints/             │
│                              │  │  Services │  │  services/                 │
│                              │  │  Models   │  │  models/                   │
│                              │  └───────────┘  │                            │
│                              └────────┬────────┘                            │
│                                       │                                      │
│                              ┌────────▼────────┐                            │
│                              │  Middleware     │                            │
│                              │  - Rate Limit   │                            │
│                              │  - Audit Log    │                            │
│                              │  - Auth/JWT     │                            │
│                              │  - CSRF         │                            │
│                              └─────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┼─────────────────────────────────────┐
│                         BACKGROUND LAYER│                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌──┴──────────┐  ┌─────────────────────┐ │
│  │  Celery     │  │  Celery     │  │  Redis      │  │  ML Models          │ │
│  │  Workers    │  │  Beat       │  │  (Cache+    │  │  (ROAS Pred,        │ │
│  │  (Tasks)    │  │  (Schedule) │  │   Queue)    │  │   Churn, LTV)       │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┼─────────────────────────────────────┐
│                           DATA LAYER  │                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌┴────────────┐  ┌─────────────────────┐ │
│  │  PostgreSQL │  │  ClickHouse │  │  MinIO/S3   │  │  Vector DB          │ │
│  │  (Primary)  │  │  (Analytics)│  │  (Files)    │  │  (Embeddings)       │ │
│  │  SQLAlchemy │  │  Events     │  │  Uploads    │  │  (Knowledge Graph)  │ │
│  │  Alembic    │  │  Time-series│  │  Exports    │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌───────────────────────────────────────┼─────────────────────────────────────┐
│                        PLATFORM LAYER │                                      │
│  ┌──────────┐ ┌──────────┐ ┌─────────┴┐ ┌──────────┐ ┌────────────────────┐ │
│  │ Meta     │ │ Google   │ │ TikTok   │ │ Snapchat │ │ LinkedIn           │ │
│  │ CAPI     │ │ Ads API  │ │ Ads API  │ │ Ads API  │ │ Ads API            │
│  │ Graph API│ │ GA4      │ │          │ │          │ │                    │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Frontend Architecture

### Stack
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite 5
- **Styling**: Tailwind CSS 3 + shadcn/ui component library
- **State Management**: Zustand (global) + React Query (server state)
- **Routing**: React Router v6
- **Charts**: Recharts
- **Maps**: Leaflet (geo analytics)
- **PDF Export**: html2canvas + jsPDF
- **Testing**: Playwright (E2E) + Vitest (unit)

### Module Structure

```
frontend/src/
├── api/               # API clients, hooks, types
├── components/        # Reusable UI components
│   ├── ui/            # shadcn/ui primitives
│   ├── dashboard/     # Dashboard-specific widgets
│   ├── landing/       # Marketing page components
│   └── charts/        # Chart wrappers
├── contexts/          # React contexts (Auth, Theme, etc.)
├── hooks/             # Custom React hooks
├── lib/               # Utilities, chart theme, formatters
├── types/             # Global TypeScript types
├── views/             # Page-level components
│   ├── operate/       # Operator dashboard pages (renamed from tenant/)
│   ├── console/       # Owner-only platform tooling (renamed from superadmin/)
│   ├── pages/         # Marketing/static pages
│   └── whatsapp/      # WhatsApp module
└── main.tsx           # Entry point
```

### Design System

Stratum uses a **token-based design system** built on shadcn/ui:

```css
/* CSS Variables in index.css */
--background:           /* Page background */
--foreground:           /* Primary text */
--card:                 /* Card surfaces */
--card-foreground:      /* Card text */
--popover:              /* Dropdown/modal surfaces */
--popover-foreground:   /* Dropdown text */
--primary:              /* Brand accent (coral) */
--primary-foreground:   /* Text on primary */
--secondary:            /* Secondary actions */
--muted:                /* Subtle backgrounds */
--muted-foreground:     /* Secondary text */
--border:               /* Dividers and borders */
--input:                /* Form field borders */
--ring:                 /* Focus rings */
--radius:               /* Border radius scale */
```

> **Note:** The audit remediation standardized most components on these tokens. Legacy modules (WhatsApp, CMS) were migrated during the 2026-04-26 sprint.

---

## Backend Architecture

### Stack
- **Framework**: FastAPI (Python 3.11)
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Auth**: JWT + session dual-mode
- **Validation**: Pydantic v2
- **Documentation**: OpenAPI auto-generated
- **Testing**: pytest + httpx

### Layered Architecture

```
api/v1/endpoints/     # HTTP routers (thin layer)
    ├── campaigns.py
    ├── trust_layer.py
    ├── autopilot.py
    └── ...

services/             # Business logic (thick layer)
    ├── campaign_service.py
    ├── trust_service.py
    ├── autopilot_service.py
    └── ...

models/               # Database models
    ├── campaign.py
    ├── trust.py
    ├── client.py
    └── ...

core/                 # Cross-cutting concerns
    ├── security.py   # Password, JWT, encryption
    ├── config.py     # Settings & env vars
    └── exceptions.py # Custom exceptions

middleware/           # Request/response processing
    ├── auth_context.py # Auth context propagation
    ├── rate_limit.py    # Throttling
    ├── audit.py         # Audit logging
    └── csrf.py          # CSRF protection
```

### Request Lifecycle

```
Client Request
    → Nginx (SSL termination, rate limit)
    → FastAPI
        → CORS Middleware
        → Rate Limit Middleware
        → Auth Middleware (JWT validation)
        → Audit Middleware (log request)
        → Router (endpoint handler)
            → Service Layer (business logic)
                → Database / Cache / External API
            → Response Model (Pydantic)
        → Response
    → Client
```

---

## Database Layer

### PostgreSQL Schema Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  organization   │────→│     users       │────→│   user_roles    │
│  (single row)   │     │  (auth+profile) │     │  (permissions)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │
         ├──────────────→┌─────────────────┐
         │               │   campaigns     │
         │               │  (ads+config)   │
         │               └─────────────────┘
         │
         ├──────────────→┌─────────────────┐
         │               │  trust_scores   │
         │               │  (daily rollup) │
         │               └─────────────────┘
         │
         ├──────────────→┌─────────────────┐     ┌─────────────────┐
         │               │    cdp_events   │────→│ cdp_profiles    │
         │               │  (raw events)   │     │ (identity res)  │
         │               └─────────────────┘     └─────────────────┘
         │
         ├──────────────→┌─────────────────┐
         │               │ autopilot_logs  │
         │               │ (actions taken) │
         │               └─────────────────┘
         │
         └──────────────→┌─────────────────┐
                         │  changelog_     │
                         │  entries        │
                         └─────────────────┘
```

> `organization` is a single-row table (STRAT-SC-001) — it replaces the
> former `tenants` table. No other table carries a `tenant_id` column.

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single Organization row** | Replaced schema-per-tenant/shared-schema multi-tenancy; no `tenant_id` column anywhere in the schema |
| **Soft deletes** (`is_deleted`) | Recovery from accidental deletion; audit trail |
| **BigInteger for financials** | Prevents integer overflow on large budgets/revenue |
| **Indexed FKs** | N+1 prevention; owner/console portfolio queries use batched GROUP BY |
| **Alembic migrations** | Version-controlled schema changes with downgrade support; fresh chain (1 revision) as of the single-client conversion |

### ClickHouse (Analytics)

High-volume event data (CDP events, platform webhooks) streams to ClickHouse for:
- Time-series analytics
- Funnel analysis
- Attribution modeling
- Real-time aggregations

---

## Data Pipeline

### Ingestion Flow

```
Platform Webhook / API Poll
    → Celery Worker (ingest task)
        → Validate & Normalize
        → Write to PostgreSQL (state)
        → Write to ClickHouse (events)
        → Trigger Trust Score Recalculation
            → If score changed → Emit Event
                → Autopilot Evaluator
                    → If action warranted → Queue Action
                        → Trust Gate Check
                            → If PASS → Execute / If BLOCK → Alert
```

### Scheduled Jobs (Celery Beat)

| Schedule | Task | Purpose |
|----------|------|---------|
| Every 5 min | Platform sync | Poll Meta/Google for fresh campaign data |
| Every 15 min | Trust score rollup | Recalculate 5-component trust score |
| Every 1 hour | Attribution variance | Compare platform-reported vs. GA4 revenue |
| Daily at 00:00 | EMQ score calculation | Event Match Quality scoring |
| Daily at 06:00 | Autopilot evaluation | Batch review campaigns for actions |
| Weekly | Churn prediction | ML model inference on account health |

---

## Trust Engine

### 5-Component Scoring

```
Trust Score = weighted_average(
    CAPI_Health       × 0.25,
    Pixel_Firing      × 0.20,
    Event_Match_Quality × 0.20,
    Attribution_Variance × 0.20,
    Autopilot_History × 0.15
)
```

### Component Details

| Component | Data Source | Threshold | Failure Mode |
|-----------|-------------|-----------|--------------|
| **CAPI Health** | Meta Conversions API deduplication rate | < 85% | Undercounted conversions |
| **Pixel Firing** | Server-side vs. browser event ratio | < 70% | Signal loss |
| **Event Match Quality** | Advanced matching coverage | < 80% | Poor attribution |
| **Attribution Variance** | Platform revenue vs. GA4 | > 15% | Data discrepancy |
| **Autopilot History** | Success rate of past actions | < 75% | Bad automation decisions |

### Trust Gate Logic

```python
class TrustGate:
    def evaluate(self, action: Action, trust_score: int) -> GateResult:
        if trust_score >= 90:
            return GateResult(verdict="PASS", mode="automatic")
        elif trust_score >= 70:
            return GateResult(verdict="PASS", mode="supervised")
        elif trust_score >= 50:
            return GateResult(verdict="HOLD", mode="approval_required")
        else:
            return GateResult(verdict="BLOCK", mode="manual_only")
```

---

## Autopilot System

### State Machine

```
┌──────────┐    evaluate    ┌──────────┐    approve    ┌──────────┐
│  MONITOR │ ─────────────→ │  QUEUED  │ ───────────→ │ EXECUTED │
└──────────┘                └──────────┘               └──────────┘
     │                           │                          │
     │ trust_score_drop          │ timeout                  │ rollback
     ▼                           ▼                          ▼
┌──────────┐                ┌──────────┐               ┌──────────┐
│  BLOCKED │                │ EXPIRED  │               │ REVERTED │
└──────────┘                └──────────┘               └──────────┘
```

### Action Types

| Action | Trigger | Safety Limit |
|--------|---------|--------------|
| Budget Increase | ROAS > threshold × 3 days | Max +20% daily |
| Budget Decrease | ROAS < threshold × 3 days | Max -30% daily |
| Pause | CPA > 2× target × 5 days | Requires approval |
| Resume | Health recovered | Auto if score > 80 |
| Label | Campaign meets criteria | No limit |

---

## Multi-Tenancy Model — HISTORICAL (removed 2026-07)

> **This entire section describes the pre-conversion architecture and no
> longer reflects the codebase.** STRAT-SC-001 removed the `Tenant`
> model, `TenantMiddleware`, `X-Tenant-ID` header handling, and every
> `tenant_id` column/index in a single pass (verified empty via
> `git grep -n "tenant_id" -- backend/app`). Kept below for historical
> context only — see `docs/single-client-conversion.md` for what
> replaced it.

### Former isolation strategy (removed)

Stratum used to run **single-database, shared-schema** multi-tenancy:
every model carried a `tenant_id` FK to a `tenants` table, and every
query filtered on it. A `TenantMiddleware` read `X-Tenant-ID`, validated
access, and set `request.state.tenant_id` for downstream services.
Cross-tenant (superadmin) endpoints used explicit `tenant_id IN (...)`
filters with batched `GROUP BY`.

### Current model

One `Organization` row (`app/base_models.py`) holds account-wide
settings (`feature_flags`, trust gate thresholds, autopilot enforcement
mode). Authorization is role-based (`owner`/`admin`/`manager`/
`analyst`/`viewer`) via `require_owner`/`require_admin` dependencies —
there is no per-request tenant resolution step, and no query needs a
tenant filter because there is only one organization's data in the
database.

---

## Security Architecture

### Authentication

| Method | Use Case | Implementation |
|--------|----------|----------------|
| **JWT** | API access, SPAs | RS256 signed, 15-min expiry, refresh tokens |
| **Session** | Server-rendered pages | Encrypted cookie, Redis-backed |
| **WhatsApp OTP** | MFA, passwordless login | Twilio Verify, 5-min expiry |
| **API Keys** | External integrations | HMAC-SHA256, scoped by permission (no tenant scoping) |

### Authorization (RBAC)

```
Role Hierarchy:

owner
    └── admin
            └── manager
                    └── analyst
                            └── viewer
```

`owner`-only routes (platform/console tooling, feature flags) use
`require_owner`; broader admin routes use `require_admin`. Permissions
are enforced via FastAPI dependencies on the endpoint, not a tenant
middleware layer (there is no tenant middleware — removed in the
single-client conversion).

### Data Protection

| Layer | Mechanism |
|-------|-----------|
| **In Transit** | TLS 1.3 (Cloudflare → Nginx → FastAPI) |
| **At Rest** | AES-256 (database volumes) |
| **PII** | SHA-256 hashing / Fernet encryption before storage |
| **Secrets** | Environment variables only; no defaults in compose files |

### Audit Logging

Every state-mutating request is logged:
- User ID, timestamp
- Action type, resource type, resource ID
- Before/after state (diff)
- IP address, user agent

---

## Deployment Architecture

### Environments

| Environment | Frontend | Backend | Database |
|-------------|----------|---------|----------|
| **Production** | Vercel (Edge) | Docker on AWS/GCP | Managed PostgreSQL |
| **Staging** | Vercel Preview | Docker on staging | Staging PostgreSQL |
| **Local** | Vite Dev Server | Docker Compose | Local PostgreSQL |

### Docker Compose

There is a single `docker-compose.yml` at the repo root (db, redis, api,
worker, scheduler, frontend, flower) — no per-tier/per-edition compose
variants. `POSTGRES_PASSWORD:?required` pattern — no default passwords.

### CI/CD Pipeline

```
Git Push
    → GitHub Actions
        → Lint (ruff, eslint)
        → Test (pytest, playwright)
        → Build (Docker image)
        → Trivy Security Scan
        → Deploy to Vercel (frontend) / Docker Registry (backend)
```

---

## Technology Stack

### Frontend

| Category | Technology | Version |
|----------|------------|---------|
| Framework | React | 18.3 |
| Language | TypeScript | 5.4 |
| Build | Vite | 5.2 |
| Styling | Tailwind CSS | 3.4 |
| Components | shadcn/ui | latest |
| State | Zustand + React Query | 4.5 + 5.28 |
| Charts | Recharts | 2.12 |
| Maps | Leaflet | 1.9 |
| Testing | Playwright + Vitest | 1.42 + 1.4 |

### Backend

| Category | Technology | Version |
|----------|------------|---------|
| Framework | FastAPI | 0.110 |
| Language | Python | 3.11 |
| ORM | SQLAlchemy | 2.0 |
| Migrations | Alembic | 1.13 |
| Validation | Pydantic | 2.6 |
| Auth | python-jose + passlib | 3.3 + 1.7 |
| Tasks | Celery + Redis | 5.3 + 7.2 |
| Testing | pytest + httpx | 8.0 + 0.27 |

### Infrastructure

| Category | Technology |
|----------|------------|
| Web Server | Nginx |
| Database | PostgreSQL 16 + ClickHouse |
| Cache/Queue | Redis 7 |
| Storage | MinIO / AWS S3 |
| Search | Meilisearch |
| Monitoring | Prometheus + Grafana |
| CDN | Cloudflare / Vercel Edge |

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| API P95 Latency | < 200ms | ~150ms |
| Dashboard Load | < 2s | ~1.8s |
| Campaign Sync Latency | < 5 min | ~3 min |
| Trust Score Recalculation | < 30s | ~20s |
| Autopilot Action Latency | < 60s | ~45s |

---

## Related Documentation

- [Feature Specifications](../04-features/feature-index.md) — Per-feature specs, API contracts, user flows
- [Setup Guide](../01-setup/local-setup.md) — Local development environment
- [Trust Engine Deep Dive](../architecture/trust-engine.md) — Algorithm and scoring details
- [Deployment Guide](../deployment/) — Production deployment procedures

# Stratum AI Platform

## Overview

Revenue Operating System with Trust-Gated Autopilot architecture.
Automation executes ONLY when signal health passes safety thresholds.

## Core Concept

```
Signal Health Check → Trust Gate → Automation Decision
       ↓                  ↓              ↓
   [HEALTHY]         [PASS]         [EXECUTE]
   [DEGRADED]        [HOLD]         [ALERT ONLY]
   [UNHEALTHY]       [BLOCK]        [MANUAL REQUIRED]
```

## Project Structure

```
/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # FastAPI routes (50+ endpoints)
│   │   ├── analytics/logic/    # Signal health, EMQ, attribution, anomalies
│   │   ├── autopilot/          # Trust gate enforcement engine
│   │   ├── auth/               # JWT, MFA, permissions
│   │   ├── core/               # Config, security, logging, websocket
│   │   ├── db/                 # Database session management
│   │   ├── middleware/         # Audit, rate limiting, security headers
│   │   ├── models/             # SQLAlchemy models (23 files)
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # External integrations & business logic
│   │   │   ├── oauth/          # OAuth provider factory
│   │   │   ├── pacing/         # Budget forecasting
│   │   │   ├── profit/         # COGS & profit tracking
│   │   │   ├── reporting/      # Report generation & scheduling
│   │   │   └── crm/            # CRM integrations
│   │   ├── stratum/            # Core domain models
│   │   └── workers/            # Celery tasks
│   ├── migrations/             # Alembic — fresh single-client chain (1 revision)
│   ├── tests/                  # pytest suite (unit/ + integration/)
│   ├── Makefile                # Build automation
│   └── requirements.txt        # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── api/                # API client wrappers
│   │   ├── components/         # React components (50+ TSX files)
│   │   ├── contexts/           # React context providers
│   │   ├── hooks/              # Custom React hooks
│   │   ├── stores/             # Zustand stores
│   │   ├── views/              # Page views & routes
│   │   └── styles/             # Tailwind CSS + custom styles
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml          # 7 services (db, redis, api, worker, scheduler, frontend, flower)
├── backend/docs/               # 60+ documentation files (curated subset is shipped in the backend image for the Copilot RAG indexer)
└── CLAUDE.md
```

## Key Features (12)

| #   | Feature               | Key Files                                                        |
| --- | --------------------- | ---------------------------------------------------------------- |
| 1   | Trust Engine          | `analytics/logic/signal_health.py`, `stratum/core/trust_gate.py` |
| 2   | CDP                   | `models/cdp.py`, `analytics/logic/emq_calculation.py`            |
| 3   | Autopilot Enforcement | `autopilot/enforcer.py`, `autopilot/service.py`                  |
| 4   | Campaign Builder      | `models/campaign_builder.py`                                     |
| 5   | Audience Sync         | `services/cdp/audience_sync/`                                    |
| 6   | Authentication        | `auth/`, `core/security.py`, `services/mfa_service.py`           |
| 7   | Analytics             | `analytics/logic/` (8 modules)                                   |
| 8   | Integrations          | `services/oauth/` (Meta, Google, TikTok, Snapchat)               |
| 9   | CMS                   | `models/cms.py`, frontend CMS editor                             |
| 10  | WhatsApp              | `services/whatsapp_service.py`                                   |
| 11  | Reporting             | `services/reporting/` (PDF, Slack, email)                        |
| 12  | Console / Owner       | `endpoints/console.py`                                           |

## Key Commands

```bash
# Backend
make dev              # Start FastAPI with hot reload (port 8000)
make test             # Run pytest
make test-all         # Run all tests with verbose output
make test-cov         # Tests with coverage report
make lint             # Ruff + mypy
make format           # Auto-format with ruff, black, isort
make migrate          # Run Alembic migrations
make migration msg="description"  # Create new migration
make check            # Lint + type check + test

# Docker
docker compose up -d              # Full stack (7 services)
docker compose --profile monitoring up -d  # Include Flower

# Frontend
cd frontend && npm run dev        # Vite dev server (port 5173)
cd frontend && npm run build      # Production build
cd frontend && npm run test       # Vitest
```

## Code Standards

- Type hints REQUIRED on all functions
- Pydantic models for all API I/O
- Async/await for all I/O operations
- 90%+ test coverage for core/
- Docstrings on public functions
- Use `datetime.now(timezone.utc)` (NOT `datetime.utcnow()`)
- Use `secrets` module for security tokens (NOT `random`)
- Use `hmac.compare_digest()` for constant-time comparisons
- Encrypt PII with Fernet before storage
- Structured logging via structlog (JSON format)

## Domain Terminology

| Term             | Definition                                     |
| ---------------- | ---------------------------------------------- |
| Signal           | Input data point (metric, event, webhook)      |
| Signal Health    | Composite score (0-100) of signal reliability  |
| Trust Gate       | Decision checkpoint before automation          |
| Autopilot        | Automated action when trust passes             |
| EMQ              | Event Match Quality - signal fidelity score    |
| CDP              | Customer Data Platform - profile & event store |
| Enforcement Mode | Advisory / Soft-Block / Hard-Block             |
| ROAS             | Return on Ad Spend                             |
| Pacing           | Budget spend velocity tracking                 |

## Trust Engine Rules

```python
# Thresholds are org-configurable (Organization settings; see TrustGateConfig)
HEALTHY_THRESHOLD = 70      # Green - autopilot enabled
DEGRADED_THRESHOLD = 40     # Yellow - alert + hold
# Never auto-execute when signal_health < 70

# Signal Health Component weights (stratum/core/signal_health.py HealthConfig):
# EMQ: 40%, Freshness: 25%, Attribution Variance: 20%, Anomaly: 15%.
# When CDP data is available the four base weights scale by 0.9 and
# CDP contributes the remaining 10%.
# The dashboard overview card uses a separate lightweight heuristic
# (Freshness 40% / EMQ 35% / Connectivity 25%) in endpoints/dashboard.py.
```

## Do NOT

- Skip trust gate checks for "quick fixes"
- Hardcode thresholds (use config)
- Execute automations without audit logging
- Merge without passing CI
- Use `random` for security tokens (use `secrets`)
- Put PII in JWT claims (use encrypted DB fields)
- Store plaintext credentials in frontend code
- Commit `.env` files or API credentials

## Testing

```bash
make test                    # Quick test run
make test-cov                # With coverage
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only
```

Test files: `backend/tests/unit/` and `backend/tests/integration/`
Coverage target: 90%+ for `core/`, `autopilot/`, `analytics/`

## Git Workflow

- Branch: `feature/STRAT-123-description`
- Commit: `feat(signals): add anomaly detection [STRAT-123]`
- Conventional commits: `feat|fix|refactor|test|docs(scope): message`

## Design Context

### Users

Marketing agencies managing multiple client accounts across ad platforms. Extended sessions, professional setting, data-heavy workflows.

### Brand Personality

**Bold, intelligent, premium.** Sophisticated power through restraint. Bloomberg terminal meets luxury brand.

### Aesthetic Direction

- **Theme**: SuperAds — dual mode, dark default. Source of truth
  `design-system-template/themes/superads.xml`. See
  `backend/docs/03-frontend/figma-theme.md` for the full token table.
- **Palette**: Navy-slate surfaces + SuperAds blue.
  - Dark: page `#0A0E1A` · surface `#141B2D` · elevated `#1C2438` · line `#1F2937` · accent `#3B82F6`.
  - Light: page `#F8FAFC` · surface `#FFFFFF` · line `#E2E8F0` · accent `#3B82F6`.
  - Data series: blue `#3B82F6` · purple `#8B5CF6` · pink `#EC4899` · green `#10B981` · cyan `#06B6D4`.
- **Typography**: Inter (body) + Space Grotesk (display) + JetBrains Mono
  (labels, status, tabular). Noto Sans Arabic for RTL surfaces.
- **Surfaces**: Elevation by drop-shadow across a three-tier stack
  (page → surface → elevated). `--bg-glass` translucency is available for
  overlay surfaces.

> **Grounding.** The template extracted fonts, accents, gradients and the
> light/dark structure from the real source, but its README flags
> **surfaces, radii, spacing, shadows and motion timings as inferred** —
> the upstream `shared/styles.css` was never provided. Those values are a
> best estimate, not measured, and should be corrected if the original
> stylesheet turns up.

**History**: this replaced an Opal Hotel gold theme (`#C2A670` on black),
which had itself replaced the original ink + ember figma theme
(`#FF5A1F`). Earlier revisions of this file described ember long after the
code had moved to gold — check `frontend/src/index.css` before trusting any
palette documented here.

### Design Principles

1. **Quiet authority** — Power through precision, not noise
2. **Information density without clutter** — Strong hierarchy, not hidden data
3. **Premium materiality** — Tinted neutrals, subtle depth, no flat gray
4. **Decisive contrast** — Bold type hierarchy, 1.5x+ ratio between steps
5. **Earn every pixel** — Every element serves the user's task
6. **Action-first home** — The dashboard is a triage queue, not a dashboard. Sort by intervention required.

### Component contract

The dashboard composes from typed primitives, not bespoke surfaces. Reuse before building:

- `frontend/src/components/primitives/Card.tsx` — surface (default / elevated / glow variants)
- `frontend/src/components/primitives/KPI.tsx` — composed Card + label + value + delta + status
- `frontend/src/components/primitives/StatusPill.tsx` — figma signature pill
- `frontend/src/components/primitives/Chart.tsx` — themed recharts wrapper (LineChart / AreaChart)
- `frontend/src/components/primitives/DataTable.tsx` — headless table with sort / loading / empty
- `frontend/src/components/primitives/ConfirmDrawer.tsx` — destructive-action gate
- `frontend/src/components/primitives/nav/Sidebar.tsx` — collapsible-group nav
- `frontend/src/components/primitives/nav/Topbar.tsx` — search + theme toggle + profile
- `frontend/src/components/primitives/theme/ThemeProvider.tsx` — dark/light/system

Each ships with a vitest. ARIA + keyboard support are first-class, not afterthoughts.

## Imports

@backend/docs/architecture/trust-engine.md
@backend/docs/integrations/README.md
@backend/docs/00-overview/glossary.md
@backend/docs/03-frontend/figma-theme.md

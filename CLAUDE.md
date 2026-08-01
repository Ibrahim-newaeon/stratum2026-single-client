# ADs Growth System Platform

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

Backend targets are in `backend/Makefile`; frontend scripts are in
`frontend/package.json`. Two that aren't obvious from either:

```bash
make migration msg="description"           # Alembic autogenerate wrapper
docker compose --profile monitoring up -d  # Flower is behind a profile
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

See the imported `backend/docs/00-overview/glossary.md` below — it
defines every term (Signal, Signal Health, Trust Gate, Autopilot, EMQ,
CDP, Enforcement Mode, ROAS, Pacing) at greater length.

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

Frontend design guidance (users, brand, aesthetic direction, principles,
component contract) lives in `frontend/CLAUDE.md`, which loads only when
working under `frontend/`.

## Imports

@backend/docs/architecture/trust-engine.md
@backend/docs/integrations/README.md
@backend/docs/00-overview/glossary.md
@backend/docs/03-frontend/figma-theme.md

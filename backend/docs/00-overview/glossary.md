# Stratum AI - Glossary

## Core Concepts

### Signal
An input data point collected from various sources including metrics, events, and webhooks. Signals are the foundation of the Trust Engine's decision-making process.

### Signal Health
A composite score (0-100) measuring the reliability and quality of signals. Used by the Trust Gate to determine if automation should proceed.

- **70-100**: Healthy (Green) - Autopilot enabled
- **40-69**: Degraded (Yellow) - Alert and hold
- **0-39**: Unhealthy (Red) - Manual intervention required

### Trust Gate
A decision checkpoint that evaluates signal health before allowing automation to execute. The gate can:
- **PASS**: Signal health meets threshold, automation proceeds
- **HOLD**: Signal health is degraded, alert only, no execution
- **BLOCK**: Signal health is unhealthy, requires manual approval

### Trust Engine
The core decision-making component that evaluates signal health before allowing automation execution. Consists of:
1. Signal Collectors
2. Health Calculator
3. Trust Gate Evaluator
4. Automation Executor

### Autopilot
Automated actions that execute when trust gate conditions are met. Autopilot can:
- Adjust campaign budgets
- Modify bidding strategies
- Pause/enable campaigns
- Scale spend based on performance

### EMQ (Event Match Quality)
A score (0-100) measuring how well tracked events match with platform data. Higher EMQ indicates better attribution accuracy.

---

## Customer Data Platform (CDP)

### Profile
A unified customer record combining data from multiple sources and touchpoints. Contains:
- Identity information
- Behavioral events
- Computed traits
- Segment memberships

### Identity Graph
A visual representation showing how different identifiers (email, phone, device IDs) connect to form a unified profile.

### Identity Resolution
The process of connecting disparate identifiers to a single customer profile:
- Anonymous → Known (via email/login)
- Known → Customer (via purchase)

### Segment
A dynamic group of profiles matching specific criteria. Segments can be:
- **Behavioral**: Based on event patterns
- **Demographic**: Based on profile attributes
- **Predictive**: Based on ML models (e.g., churn risk)

### Computed Traits
Derived attributes calculated from event history:
- Total purchases
- Days since last activity
- Average order value
- Lifetime value (LTV)

### RFM Analysis
Customer segmentation based on:
- **R**ecency: How recently did they purchase?
- **F**requency: How often do they purchase?
- **M**onetary: How much do they spend?

### Lifecycle Stage
Customer journey position:
- **Anonymous**: No identity, only device/session
- **Known**: Identified (email, login)
- **Lead**: Expressed interest
- **Customer**: Made purchase
- **Active**: Recent engagement
- **At Risk**: Declining engagement
- **Churned**: No recent activity

### Audience Sync
Push CDP segments to advertising platforms for targeting:
- Meta Custom Audiences
- Google Customer Match
- TikTok Custom Audiences
- Snapchat Audience Match

---

## Advertising & Attribution

### CAPI (Conversions API)
Server-side event tracking that sends conversion data directly to ad platforms, bypassing browser limitations.

### Attribution Model
Method for assigning credit to marketing touchpoints:
- **Last-click**: 100% credit to final touchpoint
- **First-click**: 100% credit to first touchpoint
- **Linear**: Equal credit to all touchpoints
- **Time-decay**: More credit to recent touchpoints
- **Data-driven**: ML-based credit distribution

### DDA (Data-Driven Attribution)
Machine learning approach to attribution that uses historical data to determine credit distribution.

### ROAS (Return on Ad Spend)
Revenue generated per dollar spent on advertising:
```
ROAS = Revenue / Ad Spend
```

### MER (Marketing Efficiency Ratio)
Total revenue divided by total marketing spend:
```
MER = Total Revenue / Total Marketing Spend
```

### CAC (Customer Acquisition Cost)
Total cost to acquire a new customer:
```
CAC = Total Marketing Spend / New Customers Acquired
```

### LTV (Lifetime Value)
Predicted total revenue from a customer over their lifetime:
```
LTV = Average Order Value × Purchase Frequency × Customer Lifespan
```

---

## Platform & Infrastructure

### Organization
The single-org root entity (`app/base_models.py`). Stratum AI is a
single-client deployment: one `Organization` row holds account-wide
settings (`feature_flags` jsonb, trust gate thresholds, autopilot
enforcement mode). There is no per-customer isolation layer — every
user in the deployment belongs to the same organization.

> **Historical**: earlier revisions of this platform were architected
> as multi-tenant SaaS (a `Tenant` root entity, per-tenant database
> scoping, subscription tiers gating features). That model was fully
> removed in the single-client conversion (STRAT-SC-001, 2026-07) —
> `tenant_id` no longer exists anywhere in the schema, and there is no
> tier/plan gate. See `docs/single-client-conversion.md` for the
> removal ledger.

### Feature Flag
Two independent layers control functionality (see
`docs/single-client-conversion.md` for the full architecture):
- **Env-var kill-switches** — process-wide toggles in `core/config.py`
  (e.g. `feature_knowledge_graph`, `ENABLE_PUBLIC_SIGNUP`).
- **`Organization.feature_flags`** — org-configurable overrides layered
  on top of `DEFAULT_ORG_FEATURES` (`app/features/flags.py`):
  - `feature_competitor_intel`
  - `feature_what_if_simulator`
  - `feature_automation_rules`
  - `feature_gdpr_compliance`

---

## Technical Terms

### Celery
Distributed task queue for background job processing. Used for:
- Data synchronization
- Report generation
- Scheduled tasks
- Long-running operations

### Redis
In-memory data store used for:
- Caching
- Celery message broker
- Real-time pub/sub
- Rate limiting

### WebSocket
Bidirectional communication protocol for real-time updates:
- EMQ score changes
- Incident notifications
- Autopilot mode changes
- Action status updates

### SSE (Server-Sent Events)
Unidirectional server-to-client streaming for dashboard updates.

### OAuth
Authentication protocol for connecting to ad platforms. Stratum AI implements OAuth flows for:
- Meta/Facebook
- Google Ads
- TikTok Ads
- Snapchat

### JWT (JSON Web Token)
Token-based authentication for API access. Contains:
- User ID
- Role/Permissions
- Expiration

No PII and no tenant claim — this is a single-org deployment, so there
is nothing to scope a claim to.

### MFA (Multi-Factor Authentication)
Additional security layer using TOTP (Time-based One-Time Password).

---

## Integrations

### HubSpot
CRM integration for syncing contacts and companies.

### Zoho
CRM integration for customer data synchronization.

### Slack
Notification integration for alerts and reports.

### WhatsApp Business
Customer communication channel via WhatsApp Business API.

---

## Monitoring & Observability

### Prometheus
Metrics collection system for:
- Request latency
- Error rates
- Queue depths
- System health

### Grafana
Visualization platform for Prometheus metrics.

### Sentry
Error tracking and performance monitoring service.

### Structured Logging
JSON-formatted logs with consistent fields:
- Request ID
- User ID
- Timestamp
- Event type

---

## Data & Compliance

### GDPR
General Data Protection Regulation (EU privacy law). Stratum AI supports:
- Data export
- Right to erasure
- Consent management

### CCPA
California Consumer Privacy Act. Similar to GDPR requirements.

### PII (Personally Identifiable Information)
Data that can identify an individual:
- Email addresses
- Phone numbers
- Names
- Physical addresses

### Data Hashing
One-way encryption of PII for platform sync:
- SHA-256 hashed emails
- SHA-256 hashed phone numbers
- Used for audience matching without exposing raw PII

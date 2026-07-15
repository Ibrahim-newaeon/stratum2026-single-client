# =============================================================================
# Stratum AI - API v1 Router Configuration
# =============================================================================
"""
Main API router that aggregates all endpoint routers.
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (  # Previously unregistered endpoints; Gap endpoints; SendGrid inbound webhook; Drip campaigns and push notifications
    advanced_analytics,
    analytics,
    analytics_ai,
    api_keys,
    assets,
    attribution,
    audience_sync,
    audit_services,
    auth,
    autopilot,
    autopilot_enforcement,
    campaign_builder,
    campaigns,
    capi,
    cdp,
    changelog,
    clients,
    cms,
    competitors,
    compliance,
    console,
    console_analytics,
    copilot,
    dashboard,
    data_driven_attribution,
    developer,
    drip_campaigns,
    embed_widgets,
    emq_v2,
    feature_flags,
    gdpr,
    insights,
    integrations,
    intelligence,
    knowledge_graph,
    landing_cms,
    launch_readiness,
    meta_capi,
    mfa,
    ml_training,
    newsletter,
    notifications,
    oauth,
    onboarding,
    onboarding_agent,
    outbound_integrations,
    pacing,
    predictions,
    profit,
    programmatic,
    push_notifications,
    qa_fixes,
    reporting,
    rules,
    sendgrid_webhook,
    simulator,
    slack,
    trust_layer,
    users,
    webhooks,
    whatsapp,
)
from app.auth.permissions import require_owner
from app.core.feature_gate import Feature, FeatureGate

api_router = APIRouter()

# Authentication
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

# User management
api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"],
)

# Campaigns (Module B)
api_router.include_router(
    campaigns.router,
    prefix="/campaigns",
    tags=["Campaigns"],
)

# Creative Assets / DAM (Module B)
api_router.include_router(
    assets.router,
    prefix="/assets",
    tags=["Digital Assets"],
)

# Automation Rules (Module C)
api_router.include_router(
    rules.router,
    prefix="/rules",
    tags=["Automation Rules"],
)

# Competitor Intelligence (Module D)
api_router.include_router(
    competitors.router,
    prefix="/competitors",
    tags=["Competitor Intelligence"],
)

# ML Simulator (Module A) — What-If Simulator is an Enterprise feature (P0-5)
api_router.include_router(
    simulator.router,
    prefix="/simulate",
    tags=["ML Simulator"],
    dependencies=[Depends(FeatureGate(Feature.WHAT_IF_SIMULATOR))],
)

# Analytics & Dashboard
api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Analytics"],
)

# GDPR Compliance (Module F) — GDPR tools are an Enterprise feature (P0-5)
api_router.include_router(
    gdpr.router,
    prefix="/gdpr",
    tags=["GDPR Compliance"],
    dependencies=[Depends(FeatureGate(Feature.GDPR_TOOLS))],
)

# WhatsApp Integration (Module G)
api_router.include_router(
    whatsapp.router,
    prefix="/whatsapp",
    tags=["WhatsApp"],
)
# WhatsApp webhooks: separate un-authed router (self-authenticating via
# Meta HMAC signature / hub verify token; public path per auth middleware).
api_router.include_router(
    whatsapp.webhook_router,
    prefix="/whatsapp",
    tags=["WhatsApp"],
)

# ML Training & Data Upload
# Model management operates on the GLOBAL, app-wide model registry (upload,
# train, delete .pkl artifacts) — a platform operation, not org-scoped.
# Gated to owners (ML-003): previously every endpoint here was
# unauthenticated, letting anyone upload a pickle (arbitrary-code-execution
# risk on load) or delete production models.
api_router.include_router(
    ml_training.router,
    prefix="/ml",
    tags=["ML Training"],
    dependencies=[Depends(require_owner)],
)

# Live Predictions & ROAS Optimization
api_router.include_router(
    predictions.router,
    prefix="/predictions",
    tags=["Live Predictions"],
)

# Conversion API (CAPI) Integration
api_router.include_router(
    capi.router,
    prefix="/capi",
    tags=["Conversion API"],
)

# Meta CAPI QA (Event collection with quality tracking)
api_router.include_router(
    meta_capi.router,
    tags=["Meta CAPI QA"],
)

# Landing Page CMS (Multi-language content management)
api_router.include_router(
    landing_cms.router,
    tags=["Landing CMS"],
)

# EMQ One-Click Fix System
api_router.include_router(
    qa_fixes.router,
    tags=["QA Fixes"],
)

# AI-Powered Analytics (Scaling scores, fatigue, anomalies, recommendations)
api_router.include_router(
    analytics_ai.router,
    prefix="/analytics/ai",
    tags=["AI Analytics"],
)

# Owner Console (Platform-level management)
api_router.include_router(
    console.router,
    prefix="/console",
    tags=["Owner Console"],
)

# Launch Readiness (Go-Live wizard)
api_router.include_router(
    launch_readiness.router,
    prefix="/console/launch-readiness",
    tags=["Launch Readiness"],
)

# Dashboard (Overview metrics, signal health, campaigns, settings)
# Note: dashboard.router already has prefix="/dashboard"
api_router.include_router(
    dashboard.router,
    tags=["Dashboard"],
)


# Owner Analytics (Platform-wide analytics)
api_router.include_router(
    console_analytics.router,
    prefix="/console/analytics",
    tags=["Owner Analytics"],
)

# Autopilot (Automated campaign optimization)
# Note (STRAT-SC-001/C2): autopilot.router already declares prefix="/autopilot"
# (de-tenanted from the old per-org-scoped path), so it must be mounted
# WITHOUT an extra prefix (matching autopilot_enforcement below).
api_router.include_router(
    autopilot.router,
    tags=["Autopilot"],
)

# Autopilot Enforcement (Budget/ROAS restrictions)
# Note (STRAT-SC-001/C2): autopilot_enforcement.router already has prefix
# "/autopilot/enforcement" (de-tenanted from the old per-org-scoped path)
api_router.include_router(
    autopilot_enforcement.router,
    tags=["Autopilot Enforcement"],
)

# Campaign Builder (Multi-platform campaign creation)
api_router.include_router(
    campaign_builder.router,
    prefix="/campaign-builder",
    tags=["Campaign Builder"],
)

# Feature Flags (Feature toggles and rollouts)
# Note (STRAT-SC-001/C2): feature_flags.tenant_router is now un-prefixed
# (de-tenanted from the old per-org-scoped path); feature_flags.owner_router keeps
# its "/console" prefix (renamed from "/superadmin" in B1).
api_router.include_router(
    feature_flags.router,
    tags=["Feature Flags"],
)

# AI Insights (Intelligent recommendations)
api_router.include_router(
    insights.router,
    prefix="/insights",
    tags=["AI Insights"],
)

# Trust Layer (Data quality and signal health)
api_router.include_router(
    trust_layer.router,
    prefix="/trust",
    tags=["Trust Layer"],
)

# EMQ v2 (Event Measurement Quality - Enhanced)
api_router.include_router(
    emq_v2.router,
    tags=["EMQ v2"],
)

# Integrations (HubSpot, CRM, Attribution)
api_router.include_router(
    integrations.router,
    tags=["Integrations"],
)

# Pacing & Forecasting (Targets, Pacing Alerts, EOM Projections)
api_router.include_router(
    pacing.router,
    prefix="/pacing",
    tags=["Pacing & Forecasting"],
)

# Profit ROAS (Products, COGS, Profit Calculations)
api_router.include_router(
    profit.router,
    prefix="/profit",
    tags=["Profit ROAS"],
)

# Multi-Touch Attribution (MTA)
api_router.include_router(
    attribution.router,
    tags=["Attribution"],
)

# Data-Driven Attribution (ML-based)
api_router.include_router(
    data_driven_attribution.router,
    tags=["Data-Driven Attribution"],
)

# Automated Reporting (Scheduled reports, PDF generation, multi-channel delivery)
api_router.include_router(
    reporting.router,
    prefix="/reporting",
    tags=["Automated Reporting"],
)

# Audit Services (EMQ, Offline Conversions, A/B Testing, LTV, etc.)
api_router.include_router(
    audit_services.router,
    prefix="/audit",
    tags=["Audit Services"],
)

# Newsletter & Email Campaigns
# Note: newsletter.router already has prefix="/newsletter"
api_router.include_router(
    newsletter.router,
    tags=["Newsletter"],
)

# Multi-Factor Authentication (2FA/MFA)
# Note: mfa.router already has prefix="/mfa"
api_router.include_router(
    mfa.router,
    tags=["MFA"],
)

# Onboarding (Guided setup wizard)
# Note: onboarding.router already has prefix="/onboarding"
api_router.include_router(
    onboarding.router,
    tags=["Onboarding"],
)

# OAuth (Platform authorization flows)
# Note: oauth.router already has prefix="/oauth"
api_router.include_router(
    oauth.router,
    tags=["OAuth"],
)

# Notifications (In-app notifications)
# Note: notifications.router already has prefix="/notifications"
api_router.include_router(
    notifications.router,
    tags=["Notifications"],
)

# API Keys Management
# Note: api_keys.router already has prefix="/api-keys"
api_router.include_router(
    api_keys.router,
    tags=["API Keys"],
)

# Programmatic API (authenticated by X-API-Key, not JWT)
# Note: programmatic.router already has prefix="/programmatic"
api_router.include_router(
    programmatic.router,
    tags=["Programmatic API"],
)

# CDP (Customer Data Platform)
# Note: cdp.router already has prefix="/cdp"
api_router.include_router(
    cdp.router,
    tags=["CDP"],
)

# Changelog
# Note: changelog.router already has prefix="/changelog"
api_router.include_router(
    changelog.router,
    tags=["Changelog"],
)

# Client Management
api_router.include_router(
    clients.router,
    prefix="/clients",
    tags=["Clients"],
)

# =============================================================================
# Previously Unregistered Endpoints
# =============================================================================

# CMS (Content Management System - Blog, Pages, Contact)
# Note: cms.router already has prefix="/cms"
api_router.include_router(
    cms.router,
    tags=["CMS"],
)

# Knowledge Graph (Insights, Analytics, Problem Detection)
api_router.include_router(
    knowledge_graph.router,
    prefix="/knowledge-graph",
    tags=["Knowledge Graph"],
)

# Webhooks (Inbound webhook processing)
# Note: webhooks.router already has prefix="/webhooks"
api_router.include_router(
    webhooks.router,
    tags=["Webhooks"],
)

# Slack Integration
# Note: slack.router already has prefix="/slack"
api_router.include_router(
    slack.router,
    tags=["Slack"],
)

# Onboarding Agent (AI-powered onboarding assistant)
# Note: onboarding_agent.router already has prefix="/onboarding-agent"
api_router.include_router(
    onboarding_agent.router,
    tags=["Onboarding Agent"],
)

# Embeddable Widgets (External dashboard widgets)
# Note: embed_widgets.router already has prefix="/embed-widgets"
api_router.include_router(
    embed_widgets.router,
    tags=["Embed Widgets"],
)

# CDP Audience Sync (Push segments to ad platforms)
# Note: audience_sync.router already has prefix="/cdp/audience-sync"
api_router.include_router(
    audience_sync.router,
    tags=["CDP Audience Sync"],
)

# AI Copilot Chat (Feature #4)
# Note: copilot.router already has prefix="/copilot"
api_router.include_router(
    copilot.router,
    tags=["AI Copilot"],
)

# AI Intelligence (Gap #3)
api_router.include_router(
    intelligence.router,
    prefix="/intelligence",
    tags=["AI Intelligence"],
)

# Advanced Analytics (Gap #4)
# NOTE: the router already declares prefix="/analytics/advanced"; do NOT add it
# again here or the routes mount at /analytics/advanced/analytics/advanced/*.
api_router.include_router(
    advanced_analytics.router,
    tags=["Advanced Analytics"],
)

# Compliance (Gap #5)
api_router.include_router(
    compliance.router,
    prefix="/compliance",
    tags=["Compliance"],
)

# Outbound Integrations (Gap #6)
# NOTE: the router already declares prefix="/integrations/outbound"; do NOT add
# it again here or the routes mount at
# /integrations/outbound/integrations/outbound/*.
api_router.include_router(
    outbound_integrations.router,
    tags=["Outbound Integrations"],
)

# Developer Portal (Gap #8)
# NOTE: the router already declares prefix="/developer"; do NOT add it again
# here or the routes mount at /developer/developer/*.
api_router.include_router(
    developer.router,
    tags=["Developer Portal"],
)

# SendGrid Inbound Webhook (no auth — verified by URL token)
api_router.include_router(
    sendgrid_webhook.router,
    tags=["SendGrid Webhooks"],
)

# Drip Campaigns — Automated email sequences
# Note: drip_campaigns.router has prefix="/drip-campaigns"
api_router.include_router(
    drip_campaigns.router,
    tags=["Drip Campaigns"],
)

# Push Notifications — Web Push via VAPID
# Note: push_notifications.router has prefix="/push-notifications"
api_router.include_router(
    push_notifications.router,
    tags=["Push Notifications"],
)

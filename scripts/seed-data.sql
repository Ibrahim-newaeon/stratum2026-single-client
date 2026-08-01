-- ADs Growth System Seed Data
-- Single-client conversion (STRAT-SC-001): seeds the Organization singleton
-- (id=1) and a small set of demo campaigns. The owner user is NOT seeded
-- here — use `python backend/scripts/seed_owner.py` (reads
-- SUPERADMIN_EMAIL/SUPERADMIN_PASSWORD from the environment; never commit
-- credentials to this file).

-- Organization singleton (id=1). ON CONFLICT is a true no-op re-run guard:
-- the `organization` table's only row is pinned to id=1 by
-- ck_organization_singleton, so a second run just leaves the existing row
-- untouched rather than erroring.
INSERT INTO organization (id, name, slug, branding, settings, feature_flags, enforcement_mode, onboarding_state, is_onboarded, created_at, updated_at)
VALUES (
    1,
    'ADs Growth System',
    'stratum-ai',
    '{}'::jsonb,
    '{"timezone": "UTC", "currency": "USD"}'::jsonb,
    '{"signal_health": true, "attribution_variance": true, "ai_recommendations": true, "anomaly_alerts": true, "creative_fatigue": true, "campaign_builder": true, "autopilot_level": 2}'::jsonb,
    'advisory',
    '{}'::jsonb,
    false,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- Insert some sample campaigns (global — no tenant/org dimension on
-- `campaigns` post-conversion; every deployment of this app serves one
-- organization, so campaigns need no scoping column).
INSERT INTO campaigns (platform, external_id, account_id, name, status, currency, total_spend_cents, impressions, clicks, conversions, revenue_cents, labels, is_deleted, created_at, updated_at)
SELECT
    ((ARRAY['meta', 'google', 'tiktok'])[1 + (generate_series % 3)])::adplatform,
    'camp_' || generate_series,
    'act_demo_123',
    'Campaign ' || generate_series,
    ((ARRAY['active', 'paused', 'completed'])[1 + (generate_series % 3)])::campaignstatus,
    'USD',
    (random() * 500000)::int,
    (random() * 1000000)::int,
    (random() * 50000)::int,
    (random() * 1000)::int,
    (random() * 2000000)::int,
    '["demo"]'::jsonb,
    false,
    NOW() - (random() * interval '30 days'),
    NOW()
FROM generate_series(1, 10)
ON CONFLICT DO NOTHING;

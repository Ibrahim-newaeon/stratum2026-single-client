-- =============================================================================
-- Remove fabricated ad accounts left behind by the sync_ad_accounts mock
-- STRAT-CB-001 · companion to PR #63
-- =============================================================================
--
-- Until STRAT-CB-001, workers/campaign_builder_tasks.py::sync_ad_accounts did
-- not call any platform API. It wrote two invented rows per platform into
-- ad_account on every run, and the daily sync_all_ad_accounts beat kept them
-- refreshed:
--
--     act_{platform}_001   "Main Business Account"   SAR   Asia/Riyadh
--     act_{platform}_002   "E-commerce Store"        SAR   Asia/Riyadh
--
-- Nothing marked them synthetic, so they are indistinguishable from real rows
-- in the API and the UI. PR #63 stops new ones being written; it does NOT
-- remove existing ones, and after that PR the real sync will never touch them
-- again (it only updates accounts the provider actually returns). They would
-- sit orphaned indefinitely with a frozen last_synced_at.
--
-- RUN THE INSPECTION STEPS FIRST. Do not skip to step 3.
--
-- Matching is on the eight exact identifiers the mock could produce, not a
-- LIKE pattern. Real Meta account ids are act_<digits>, so a pattern such as
-- 'act\_%\_001' would not match a genuine account today — but exact ids cost
-- nothing and cannot be surprised by a provider changing its id format.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- STEP 1 (read-only) — what is actually there?
-- -----------------------------------------------------------------------------
-- Confirm the rows look like the mock's output before deleting anything. If
-- currency/timezone are NOT 'SAR'/'Asia/Riyadh', or the names differ, STOP:
-- something else created these and this script is the wrong tool.

SELECT
    id,
    platform,
    platform_account_id,
    name,
    business_name,
    currency,
    timezone,
    is_enabled,
    last_synced_at
FROM ad_account
WHERE platform_account_id IN (
    'act_meta_001',     'act_meta_002',
    'act_google_001',   'act_google_002',
    'act_tiktok_001',   'act_tiktok_002',
    'act_snapchat_001', 'act_snapchat_002'
)
ORDER BY platform, platform_account_id;


-- -----------------------------------------------------------------------------
-- STEP 2 (read-only) — THE IMPORTANT ONE: what is attached to them?
-- -----------------------------------------------------------------------------
-- campaign_draft.ad_account_id is ON DELETE SET NULL. Deleting a fake account
-- will NOT fail if drafts reference it — it will silently null the link and
-- leave a draft pointing at nothing. Any row this returns must be dealt with
-- deliberately (reassign to a real account, or delete the draft) BEFORE step 3.
--
-- An empty result here is the green light. A non-empty result is a stop.

SELECT
    d.id            AS draft_id,
    d.name          AS draft_name,
    d.status        AS draft_status,
    d.created_by_user_id,
    a.platform_account_id AS attached_to
FROM campaign_draft d
JOIN ad_account a ON a.id = d.ad_account_id
WHERE a.platform_account_id IN (
    'act_meta_001',     'act_meta_002',
    'act_google_001',   'act_google_002',
    'act_tiktok_001',   'act_tiktok_002',
    'act_snapchat_001', 'act_snapchat_002'
)
ORDER BY d.created_at;


-- -----------------------------------------------------------------------------
-- STEP 3 (destructive) — delete, inside an explicit transaction
-- -----------------------------------------------------------------------------
-- Run this ONLY after step 1 confirms the rows are the mock's and step 2
-- returns zero rows.
--
-- The transaction is left OPEN on purpose. Read the RETURNING output, satisfy
-- yourself it lists exactly what step 1 showed and nothing more, then issue
-- COMMIT by hand. ROLLBACK if anything is unexpected. Do not wrap this in a
-- script that auto-commits.

BEGIN;

DELETE FROM ad_account
WHERE platform_account_id IN (
    'act_meta_001',     'act_meta_002',
    'act_google_001',   'act_google_002',
    'act_tiktok_001',   'act_tiktok_002',
    'act_snapchat_001', 'act_snapchat_002'
)
RETURNING id, platform, platform_account_id, name;

-- Expected: only rows step 1 listed. Then, by hand:
--     COMMIT;
-- or, if anything looks wrong:
--     ROLLBACK;


-- -----------------------------------------------------------------------------
-- STEP 4 (read-only, after COMMIT) — verify, and re-sync
-- -----------------------------------------------------------------------------
-- Should return 0.
--
--     SELECT count(*) FROM ad_account
--     WHERE platform_account_id IN ('act_meta_001', 'act_meta_002',
--         'act_google_001', 'act_google_002', 'act_tiktok_001',
--         'act_tiktok_002', 'act_snapchat_001', 'act_snapchat_002');
--
-- Then, for each connected platform, trigger a real sync so the table is
-- repopulated from the provider:
--
--     celery -A app.workers.celery_app call \
--         app.workers.campaign_builder_tasks.sync_ad_accounts --args='["meta"]'
--
-- or simply wait for the daily sync_all_ad_accounts beat.
-- =============================================================================

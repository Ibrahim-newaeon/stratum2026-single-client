# Campaign Publish — Path to Operational

Status: **proposed**, not started. Written 2026-08-01.

Scope of this document: making campaign publishing genuinely work for
**Meta only**, including selection of an existing Facebook Page post or
Instagram media as the ad creative. Google Ads, TikTok, and Snapchat are
explicitly deferred — see [Why Meta first](#why-meta-first).

---

## Current state

`enable_campaign_publish` defaults to `False` (`core/config.py:477`), and
that flag is the only thing standing between this codebase and a serious
problem.

The publish path does not call any platform API. It fabricates success:

```python
# workers/campaign_builder_tasks.py:347
# Publish to platform API
# In production: result = publish_to_platform(...)

# Mock success
platform_campaign_id = f"camp_{draft_id[:8]}"
draft.status = DraftStatus.PUBLISHED
publish_log.result_status = PublishResult.SUCCESS
```

The endpoint (`endpoints/campaign_builder.py:781-791`) does not even
dispatch that task — it inlines the same fake inline, writes
`PublishResult.SUCCESS` into `CampaignPublishLog`, and stamps
`published_at`. A synthetic `camp_1a2b3c4d` identifier lands in the table
that is supposed to be the audit record of money spent.

Beyond the fake, the following do not exist:

| Missing                                   | Evidence                                                      |
| ----------------------------------------- | ------------------------------------------------------------- |
| `_create_ad` handler                      | `meta_adapter.py:681` docstring promises it; the `elif` chain at `:690` never wires it |
| Ad creative creation                      | `object_story_spec` appears nowhere in the backend             |
| Existing-post reference                   | `object_story_id` / `effective_object_story_id` appear nowhere |
| Page / IG asset listing                   | no equivalent of `ads_get_ig_media`                            |
| Typed draft schema                        | `draft_json` is untyped `JSONB`; no `schemas/campaign_builder.py` exists |
| Trust gate on publish                     | no `trust` reference in `endpoints/campaign_builder.py`        |
| Draft authoring UI                        | only `api/campaignBuilder.ts` and read-only `PublishLogs.tsx`  |

So the builder tops out at campaign + ad set, with new-upload creatives
only, behind a stub that lies about the outcome.

---

## Two decisions this plan commits to

### The MCP connector is a spec oracle, not a runtime dependency

The claude.ai Facebook connector (`mcp.facebook.com/ads`) exposes very
nearly every missing capability listed above — `ads_create_creative`,
`ads_create_ad`, `ads_get_ig_media`, and even a single-call
`ads_boost_ig_post`. It is tempting to route production traffic through
it. This plan does not, for four reasons:

1. **Auth model mismatch.** The connector authenticates through an
   interactive, user-mediated claude.ai OAuth flow.
   `services/oauth/meta.py` stores per-connection Fernet-encrypted tokens
   the backend owns and can revoke. Routing through MCP introduces a
   second Meta auth path with no `PlatformConnection` row behind it.
2. **No audit trail.** `CampaignPublishLog` is the record of what was
   spent and by whom. An LLM-mediated tool call does not populate it.
3. **Non-deterministic substrate for money-moving actions.** This is the
   heaviest objection because it cuts against the product's own thesis.
   Trust-Gated Autopilot exists so automation fires only when signal
   health passes. A tool call whose arguments are model-generated cannot
   be gated deterministically — it puts an LLM inside the enforcement
   boundary the architecture exists to keep clean.
4. **Availability.** Interactively-authenticated MCP servers are absent
   in headless and cron contexts, which is exactly where the Celery
   publish task runs.

What the connector is genuinely excellent for is **capturing ground
truth** before the adapter is written. See [Phase 0.5](#phase-05).

### Why Meta first

Of the four ad platforms, only Meta has an MCP connector. Google Ads,
TikTok Ads, and Snapchat Ads have none. (`Windsor.ai` is connected but
unauthenticated; it aggregates marketing data read-only and cannot create
campaigns or creatives.)

That asymmetry matters for scheduling: Phase 0.5 works only for Meta.
The other three adapters get written the traditional way against
documented REST APIs, with fixtures hand-built from sandbox accounts.

The sequencing consequence is the real argument. Meta first means the
canonical `draft_json` schema (Phase 2) gets designed against **observed**
payloads rather than inferred ones, then ported to the other adapters
once proven. The reverse order means designing the schema blind and
reworking every adapter when Meta's reality lands.

---

## Phases

### P0 — Stop fabricating success

**Ship standalone, independent of everything below.** Half a day.

- `workers/campaign_builder_tasks.py:347` — replace the mock block with
  `raise NotImplementedError`. The surrounding `except` already sets
  `PublishResult.FAILURE` and `DraftStatus.FAILED`, which is the correct
  behaviour.
- `endpoints/campaign_builder.py:781-791` — delete the inline fake.
  Return `501` while the adapter is unbuilt.
- Test: with the flag on, publishing fails loudly and the log records
  `FAILURE`.

A stub that fails loudly is safe. One that logs `SUCCESS` is a trap: the
first person to flip the flag for a smoke test gets green checkmarks and
no ads, and the audit table silently becomes fiction.

### Phase 0.5 — MCP discovery → fixtures

2–3 days. **Requires explicit go-ahead** — touches the live ad account,
and the boost step spends real money.

Read-only first: `ads_get_ad_accounts`, `ads_get_user_pages`,
`ads_get_ig_accounts`, `ads_get_ig_media`, `ads_get_creatives`,
`ads_get_field_context`, `ads_get_errors`.

Then one minimum-budget `ads_boost_ig_post`, followed by reading back the
resulting creative to observe exactly what a correct existing-post boost
looks like on the wire.

Questions this answers that documentation does not answer reliably:

- The authoritative `object_story_spec` shape for the current API version
- The `effective_object_story_id` format, and how it differs between a
  Facebook Page post and an Instagram media object
- Whether the field is `instagram_actor_id` or `instagram_user_id` —
  Meta renamed this and the public docs disagree with each other
- Real error payload shapes, so the adapter's error taxonomy is built
  from truth

**Deliverable:** recorded JSON in `backend/tests/fixtures/meta/`, which
becomes the test suite for Phases 1–4, plus a written spec of
`object_story_spec` covering both the FB-post and IG-media cases.

This phase probably removes a week from Phase 3, where the FB-post vs
IG-media asymmetry normally bites.

### Phase 1 — Scopes and asset discovery

3–4 days.

`META_DEFAULT_SCOPES` (`services/oauth/meta.py:48`) currently requests
`ads_management`, `ads_read`, `business_management`,
`pages_read_engagement`. Add `pages_show_list`, `instagram_basic`,
`pages_manage_ads`.

> **Adding scopes forces every existing connection to re-consent.** Land
> this before anyone connects in earnest. Needs a scope-diff check on
> `PlatformConnection.scopes` and a reconnect prompt in the UI, or
> connections silently 403 on the new calls.

New adapter methods and endpoints under `/campaign-builder/assets/`:
`list_pages`, `list_ig_accounts`, `list_page_posts`, `list_ig_media`.
Tested against Phase 0.5 fixtures.

### Phase 2 — Canonical draft schema

2–3 days. **Deliberately before the adapter work** — `draft_json` is
untyped and everything downstream depends on its shape.

New `backend/app/schemas/campaign_builder.py`:

```
CampaignSpec → AdSetSpec → AdSpec → CreativeSpec
```

`CreativeSpec` is a discriminated union, and this is where the requested
feature actually lives:

- `NewCreative` — `image_hash` / `video_id` from the existing
  `upload_image` / `upload_video`
- `ExistingPostCreative` — `object_story_id` for a Page post, or
  `ig_media_id` for Instagram media

Validate on write in `POST /campaign-drafts`. Check for existing drafts
in production before assuming no backfill is needed.

### Phase 3 — Creative and ad layer

4–5 days.

- `_create_ad_creative` on the Meta adapter, building `object_story_spec`
  for both `CreativeSpec` variants
- `_create_ad`, wired into the action router at `meta_adapter.py:690`
  where `create_ad` currently falls through to `else`
- Correct the `:681` docstring that already claims support

### Phase 4 — Real publish orchestration

4–5 days. The hard one.

Four sequential Graph calls: campaign → ad set → creative → ad.

- **Partial failure.** If the creative is created and the ad fails, there
  is an orphaned creative and a draft in a state that is neither
  published nor clean. Add `DraftStatus.PARTIAL` and record each real ID
  into `publish_log.response_json` *incrementally as it is created*, so a
  mid-sequence failure leaves a recoverable trail.
- **Idempotency.** The task is `max_retries=3`, and a blanket retry would
  currently re-run the whole sequence and double-create. Meta has no
  universal idempotency key, so each step must check
  `publish_log.response_json` for an already-recorded ID before firing.

### Phase 5 — Trust gate

2 days.

Gate `POST /campaign-drafts/{id}/publish` on signal health, per the
project's own rules, and emit an audit log on the mutation. Publishing is
presently the one money-moving write path in the system that bypasses the
gate entirely.

### Phase 6 — Frontend

2–3 weeks. Greenfield — there is no draft authoring UI at all today.

Draft wizard, plus the post picker the original question was about:
Page / IG account selector → media grid → preview. Composed from the
primitives in the CLAUDE.md component contract, not bespoke surfaces.

### Phase 7 — Enablement

End-to-end against a sandbox ad account, then flip
`enable_campaign_publish`.

---

## Parallel tracks

### Track X — Meta App Review (start day 1)

`ads_management`, `pages_show_list`, `instagram_basic`, and
`pages_manage_ads` are all App Review permissions. Beyond your own
dev-mode assets, production requires Business Verification plus an App
Review submission with a screencast. Typically **2–6 weeks of calendar
time**, and no amount of engineering shortens it.

**This is the critical path, not the code.** Start it immediately.

### Track B — Operator agents (optional, independent)

Scheduled cloud agents with the Facebook connector attached, for
read-only work the backend has no reason to own: weekly performance
sweeps, `ads_library_search` competitive checks,
`ads_insights_anomaly_signal` triage. Additive, does not duplicate the
adapter, could ship in 1–2 days regardless of everything above.

---

## Estimate

Backend Phases P0–5: roughly **3–4 weeks**. Frontend Phase 6: **2–3
weeks**, partly parallelisable. Gated throughout on Track X.

The "select an existing post" feature is a thin slice across Phases
0.5, 1, 2, 3, and 6. It cannot ship early, because there is currently no
ad level in the draft at all.

## Porting to other platforms

After Meta proves the `CreativeSpec` shape, port to Google, TikTok, and
Snapchat. Expect these to feel slower than Meta — that is the missing
MCP fixture shortcut, not a problem with the adapters. All three have
solid documented APIs.

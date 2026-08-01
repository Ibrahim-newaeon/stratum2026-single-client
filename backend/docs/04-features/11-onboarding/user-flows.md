# Onboarding Wizard User Flows

## Overview

Step-by-step user journeys for the onboarding experience.

---

## Flow 1: Complete Onboarding (Happy Path)

**Actor**: New Tenant Admin
**Goal**: Complete initial platform configuration

### Steps

1. User signs up and creates account
2. Dashboard redirects to onboarding wizard
3. User completes Step 1: Business Profile
4. User completes Step 2: Platform Selection
5. User completes Step 3: Goals Setup
6. User completes Step 4: Automation Preferences
7. User completes Step 5: Trust Gate Configuration
8. Wizard shows completion confirmation
9. User redirected to dashboard

### Wizard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Welcome to ADs Growth System                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Let's set up your account                                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ● ─── ○ ─── ○ ─── ○ ─── ○                           │   │
│  │ 1     2     3     4     5                           │   │
│  │ Business  Platform  Goals  Automation  Trust        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │           [Current Step Content]                    │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [◀ Back]                              [Continue ▶]        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 2: Step 1 - Business Profile

**Actor**: New Tenant Admin
**Goal**: Provide business information

### Steps

1. User sees business profile form
2. User enters company name
3. User selects industry from dropdown
4. User selects monthly ad spend range
5. User selects team size
6. User enters website URL (optional)
7. User confirms timezone
8. User clicks "Continue"
9. Data saved, proceed to Step 2

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Tell us about your business                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Company Name *                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Acme Corporation                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Industry *                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ E-Commerce                                      ▼   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Monthly Ad Spend *                                         │
│  ○ Under $10K                                               │
│  ● $10K - $50K                                              │
│  ○ $50K - $100K                                             │
│  ○ $100K - $500K                                            │
│  ○ Over $500K                                               │
│                                                             │
│  Team Size *                                                │
│  ○ Just me        ● 2-5 people    ○ 6-20 people            │
│  ○ 21-50 people   ○ 50+ people                              │
│                                                             │
│  Website (optional)                                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ https://acme.com                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Timezone *                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ America/Los_Angeles (PST)                       ▼   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [◀ Back]                                   [Continue ▶]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 3: Step 2 - Platform Selection

**Actor**: New Tenant Admin
**Goal**: Select and optionally connect ad platforms

### Steps

1. User sees platform selection cards
2. User selects one or more platforms
3. User clicks on platform to connect (optional)
4. Connection modal opens
5. User enters credentials
6. User tests connection
7. Connection saved
8. User can skip connection ("Connect later")
9. User clicks "Continue"

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Select your advertising platforms                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Which platforms do you advertise on?                       │
│                                                             │
│  ┌──────────────────────┐ ┌──────────────────────┐         │
│  │  📘 Meta Ads         │ │  📗 Google Ads       │         │
│  │  ☑ Selected          │ │  ☑ Selected          │         │
│  │  ○ Not connected     │ │  ● Connected ✓       │         │
│  │                      │ │                      │         │
│  │  [Connect Now]       │ │  [Reconnect]         │         │
│  └──────────────────────┘ └──────────────────────┘         │
│                                                             │
│  ┌──────────────────────┐ ┌──────────────────────┐         │
│  │  📙 TikTok Ads       │ │  👻 Snapchat Ads     │         │
│  │  ☐ Not selected      │ │  ☐ Not selected      │         │
│  │                      │ │                      │         │
│  │                      │ │                      │         │
│  │  [Select]            │ │  [Select]            │         │
│  └──────────────────────┘ └──────────────────────┘         │
│                                                             │
│  ⓘ You can connect platforms later from Settings           │
│                                                             │
│  Primary Platform (optional):                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Google Ads                                      ▼   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [◀ Back]                                   [Continue ▶]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 4: Step 3 - Goals Setup

**Actor**: New Tenant Admin
**Goal**: Define business goals and KPIs

### Steps

1. User sees goals configuration
2. User selects primary KPI
3. User enters target value for KPI
4. User optionally sets budget target
5. User optionally sets revenue goal
6. User clicks "Continue"

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Define your goals                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  What's your primary success metric?                        │
│                                                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ ● ROAS       │ │ ○ CPA        │ │ ○ Revenue    │        │
│  │ Return on    │ │ Cost per     │ │ Total        │        │
│  │ Ad Spend     │ │ Acquisition  │ │ Revenue      │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                             │
│  ┌──────────────┐ ┌──────────────┐                          │
│  │ ○ Conversions│ │ ○ Leads      │                          │
│  │ Total        │ │ Lead         │                          │
│  │ Conversions  │ │ Generation   │                          │
│  └──────────────┘ └──────────────┘                          │
│                                                             │
│  Target ROAS *                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2.5                                              x   │   │
│  └─────────────────────────────────────────────────────┘   │
│  ⓘ We'll optimize campaigns to achieve 2.5x ROAS          │
│                                                             │
│  Monthly Budget Target (optional)                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ $25,000                                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Revenue Goal (optional)                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ $62,500                                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [◀ Back]         [Skip this step]          [Continue ▶]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 5: Step 4 - Automation Preferences

**Actor**: New Tenant Admin
**Goal**: Configure automation behavior

### Steps

1. User sees automation mode options
2. User selects preferred mode
3. User enables/disables specific automations
4. User configures notification preferences
5. User clicks "Continue"

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Automation preferences                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  How hands-on do you want to be?                           │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ○ Conservative                                      │   │
│  │   Advisory only - all actions require your approval │   │
│  │   Best for: New users, learning the platform        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ● Moderate (Recommended)                            │   │
│  │   Smart automation with safety confirmations        │   │
│  │   Best for: Balanced control and efficiency         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ○ Aggressive                                        │   │
│  │   Full autopilot when signal health is good         │   │
│  │   Best for: High volume, experienced users          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Enable these automations:                                  │
│  ☑ Auto-pause underperforming campaigns                    │
│  ☑ Automatic budget adjustments                            │
│  ☐ Auto-enable paused campaigns when recovered             │
│                                                             │
│  Notifications:                                             │
│  ☑ Email alerts for important changes                      │
│  ☐ Slack notifications                                      │
│                                                             │
│  [◀ Back]         [Skip this step]          [Continue ▶]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 6: Step 5 - Trust Gate Configuration

**Actor**: New Tenant Admin
**Goal**: Set safety thresholds

### Steps

1. User sees trust gate settings
2. Default values pre-filled based on automation mode
3. User adjusts signal health threshold
4. User sets ROAS threshold
5. User configures budget limits
6. User sets cooldown period
7. User clicks "Complete Setup"

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Step 5: Configure safety controls                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  These settings protect your campaigns from risky changes   │
│                                                             │
│  Signal Health Threshold                                    │
│  ─────────────────────────────────○──────── 70%            │
│  Actions only execute when signal health is above 70%       │
│                                                             │
│  Minimum ROAS for Automation                                │
│  ─────────────────○──────────────────────── 1.0x           │
│  Budget increases blocked below this ROAS                   │
│                                                             │
│  Maximum Budget Increase                                    │
│  ─────────────────────○────────────────────  20%           │
│  Single change cannot increase budget by more than 20%      │
│                                                             │
│  Maximum Budget Decrease                                    │
│  ────────────────────────────○─────────────  30%           │
│  Single change cannot decrease budget by more than 30%      │
│                                                             │
│  Cooldown Between Changes                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 24 hours                                        ▼   │   │
│  └─────────────────────────────────────────────────────┘   │
│  Minimum time between budget changes to the same campaign  │
│                                                             │
│  ☑ Require confirmation for changes exceeding thresholds   │
│                                                             │
│  [◀ Back]         [Skip this step]     [Complete Setup ▶]  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 7: Resume Onboarding

**Actor**: Returning User
**Goal**: Continue incomplete onboarding

### Steps

1. User logs in with incomplete onboarding
2. Dashboard shows onboarding banner
3. User clicks "Continue Setup"
4. Wizard opens at last incomplete step
5. Previous steps show as complete
6. User continues from where they left off

### Resume Banner

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ⓘ You're 60% through setup                                │
│                                                             │
│  Complete your onboarding to unlock all features.          │
│  You're currently on: Goals Setup                           │
│                                                             │
│  [Continue Setup]                         [Dismiss for now] │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 8: Skip Optional Step

**Actor**: New Tenant Admin
**Goal**: Skip an optional configuration step

### Steps

1. User is on an optional step (3, 4, or 5)
2. User clicks "Skip this step"
3. Confirmation modal appears
4. Modal explains default values will be used
5. User confirms skip
6. Step marked as "Skipped"
7. User proceeds to next step

### Skip Confirmation

```
┌─────────────────────────────────────────────────────────────┐
│  Skip Goals Setup?                                    [×]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  If you skip this step, we'll use these defaults:          │
│                                                             │
│  • Primary KPI: ROAS                                        │
│  • Target ROAS: 2.0x                                        │
│  • No specific budget or revenue targets                   │
│                                                             │
│  You can change these settings later in Settings → Goals.  │
│                                                             │
│  [Go Back]                              [Skip & Continue]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 9: Completion Celebration

**Actor**: New Tenant Admin
**Goal**: Celebrate setup completion

### Steps

1. User completes final step
2. Confetti animation displays
3. Summary of configured settings shown
4. Next steps suggested
5. User clicks to go to dashboard

### Completion Screen

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                    🎉 You're all set!                       │
│                                                             │
│  Your ADs Growth System account is ready to go.                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Summary                                             │   │
│  │                                                     │   │
│  │ ✓ Business: Acme Corporation (E-Commerce)          │   │
│  │ ✓ Platforms: Meta Ads, Google Ads                   │   │
│  │ ✓ Primary KPI: ROAS (Target: 2.5x)                  │   │
│  │ ✓ Automation: Moderate                              │   │
│  │ ✓ Trust Gate: 70% threshold                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  What's next?                                               │
│  • Import your first campaign                               │
│  • Set up your first automation rule                       │
│  • Explore the dashboard                                    │
│                                                             │
│              [Go to Dashboard]                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- [Specification](./spec.md) - Data models and architecture
- [API Contracts](./api-contracts.md) - API endpoints and schemas
- [Edge Cases](./edge-cases.md) - Error handling and edge cases

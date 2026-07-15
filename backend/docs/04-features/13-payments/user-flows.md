# Payments & Billing User Flows

> **REMOVED (historical) — 2026-07**: the Payments feature was fully
> removed in the single-client conversion (STRAT-SC-001). Kept for
> historical reference only — see `docs/single-client-conversion.md`.

## Overview

Step-by-step user journeys for subscription management and billing.

---

## Flow 1: Start Free Trial

**Actor**: New User
**Goal**: Begin 14-day free trial

### Steps

1. User completes signup
2. Trial automatically starts
3. User selects plan preference
4. Dashboard shows trial status
5. Trial countdown displayed

### Trial Banner

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  🎉 You're on a 14-day free trial of Growth Plan           │
│                                                             │
│  12 days remaining                                          │
│  [Add Payment Method]              [View Plans]             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 2: Subscribe to Plan

**Actor**: Tenant Admin
**Goal**: Subscribe to a paid plan

### Steps

1. User clicks "Upgrade" or trial expires
2. Plan selection page displays
3. User compares plans
4. User selects plan (Monthly/Annual)
5. User enters payment method
6. User reviews order summary
7. User confirms subscription
8. Subscription activated

### Plan Selection

```
┌─────────────────────────────────────────────────────────────┐
│  Choose Your Plan                   [Monthly ●] [Annual ○] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐ ┌──────────────────┐ ┌────────────┐  │
│  │     STARTER      │ │      GROWTH      │ │ ENTERPRISE │  │
│  │                  │ │    RECOMMENDED   │ │            │  │
│  │     $99/mo       │ │     $299/mo      │ │   Custom   │  │
│  │                  │ │                  │ │            │  │
│  │ ✓ 10 Campaigns   │ │ ✓ 50 Campaigns   │ │ ✓ Unlimited│  │
│  │ ✓ 50K Events     │ │ ✓ 250K Events    │ │ ✓ Unlimited│  │
│  │ ✓ 2 Team Members │ │ ✓ 10 Team Members│ │ ✓ Unlimited│  │
│  │ ✓ 2 Platforms    │ │ ✓ All Platforms  │ │ ✓ All      │  │
│  │ ✓ Basic Support  │ │ ✓ Priority Support│ │ ✓ Dedicated│  │
│  │                  │ │ ✓ API Access     │ │ ✓ Custom   │  │
│  │                  │ │ ✓ WhatsApp       │ │            │  │
│  │                  │ │                  │ │            │  │
│  │   [Select]       │ │   [Select]       │ │ [Contact]  │  │
│  └──────────────────┘ └──────────────────┘ └────────────┘  │
│                                                             │
│  Save 17% with annual billing                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 3: Add Payment Method

**Actor**: Tenant Admin
**Goal**: Add credit card for billing

### Steps

1. User navigates to Billing → Payment Methods
2. User clicks "Add Card"
3. Stripe Elements form displays
4. User enters card details
5. Card validated with Stripe
6. Card added and set as default

### Payment Form

```
┌─────────────────────────────────────────────────────────────┐
│  Add Payment Method                                   [×]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Card Number                                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 4242 4242 4242 4242                            💳   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Expiry                    CVC                              │
│  ┌───────────────────┐    ┌───────────────────┐            │
│  │ 12 / 25           │    │ 123               │            │
│  └───────────────────┘    └───────────────────┘            │
│                                                             │
│  Billing Address                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 123 Main Street                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  City                      State        ZIP                 │
│  ┌──────────────────┐    ┌────────┐   ┌──────────┐        │
│  │ San Francisco    │    │ CA     │   │ 94102    │        │
│  └──────────────────┘    └────────┘   └──────────┘        │
│                                                             │
│  ☑ Set as default payment method                           │
│                                                             │
│  [Cancel]                                    [Add Card]     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 4: Upgrade Plan

**Actor**: Tenant Admin
**Goal**: Upgrade from Starter to Growth

### Steps

1. User navigates to Billing → Subscription
2. User clicks "Upgrade Plan"
3. Available upgrade shown
4. Proration calculated and displayed
5. User confirms upgrade
6. New limits apply immediately
7. Invoice adjusted

### Upgrade Confirmation

```
┌─────────────────────────────────────────────────────────────┐
│  Upgrade to Growth                                    [×]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Current Plan: Starter ($99/mo)                             │
│  New Plan: Growth ($299/mo)                                 │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ What You'll Get                                     │   │
│  │                                                     │   │
│  │ ✓ 50 Campaigns (was 10)                            │   │
│  │ ✓ 250K Events/mo (was 50K)                         │   │
│  │ ✓ 10 Team Members (was 2)                          │   │
│  │ ✓ All Platforms (was 2)                            │   │
│  │ ✓ Priority Support                                 │   │
│  │ ✓ API Access                                       │   │
│  │ ✓ WhatsApp Integration                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Prorated Charge Today                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Remaining days: 15                                  │   │
│  │ Starter credit: -$49.50                             │   │
│  │ Growth charge: $149.50                              │   │
│  │ ────────────────────────                            │   │
│  │ Amount due: $100.00                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Cancel]                              [Confirm Upgrade]    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 5: View Usage

**Actor**: Tenant Admin
**Goal**: Monitor current usage against limits

### Steps

1. User navigates to Billing → Usage
2. Current period usage displayed
3. Comparison to plan limits shown
4. Historical usage available
5. Overage warnings if approaching limits

### Usage Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│  Usage This Month                      Billing Period: Jan │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Campaigns                                                  │
│  ████████████████████░░░░░░░░░░░░░░  8 / 10                │
│  80% of limit used                                          │
│                                                             │
│  Events                                                     │
│  ██████████████░░░░░░░░░░░░░░░░░░░░  35,240 / 50,000       │
│  70% of limit used                                          │
│                                                             │
│  Team Members                                               │
│  ██████████░░░░░░░░░░░░░░░░░░░░░░░░  2 / 2                 │
│  At limit - [Upgrade to add more]                          │
│                                                             │
│  API Calls                                                  │
│  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  12,450 / Unlimited    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Usage Trend (Last 6 Months)                         │   │
│  │                                                     │   │
│  │   ▁▂▃▄▅▆                                           │   │
│  │   Aug Sep Oct Nov Dec Jan                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 6: View Invoices

**Actor**: Tenant Admin
**Goal**: Access billing history and invoices

### Steps

1. User navigates to Billing → Invoices
2. Invoice list displayed
3. User clicks invoice to view details
4. User can download PDF
5. User can pay outstanding invoices

### Invoice List

```
┌─────────────────────────────────────────────────────────────┐
│  Invoices                                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Invoice        Date         Amount      Status             │
│  ─────────────────────────────────────────────────────────  │
│  INV-2024-01    Jan 1, 2024   $299.00    ● Paid             │
│  INV-2023-12    Dec 1, 2023   $299.00    ● Paid             │
│  INV-2023-11    Nov 1, 2023   $299.00    ● Paid             │
│  INV-2023-10    Oct 1, 2023   $99.00     ● Paid             │
│  INV-2023-09    Sep 1, 2023   $99.00     ● Paid             │
│                                                             │
│  [◀ Previous]                            [Next ▶]           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 7: Cancel Subscription

**Actor**: Tenant Admin
**Goal**: Cancel subscription

### Steps

1. User navigates to Billing → Subscription
2. User clicks "Cancel Subscription"
3. Retention modal appears
4. User selects cancellation reason
5. User confirms cancellation
6. Subscription set to cancel at period end
7. Access continues until period end

### Cancellation Flow

```
┌─────────────────────────────────────────────────────────────┐
│  We're sorry to see you go                            [×]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Before you cancel, would you like to:                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 💰 Switch to Starter plan ($99/mo)                  │   │
│  │    Keep access to core features at a lower price    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ⏸️ Pause your subscription (up to 3 months)         │   │
│  │    Keep your data, resume anytime                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 💬 Talk to our team                                 │   │
│  │    We'd love to understand how we can help         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Why are you canceling? (optional)                         │
│  ○ Too expensive                                            │
│  ○ Missing features I need                                  │
│  ○ Not using it enough                                      │
│  ○ Switching to competitor                                  │
│  ○ Other                                                    │
│                                                             │
│  [Keep Subscription]              [Confirm Cancellation]    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 8: Handle Failed Payment

**Actor**: Tenant Admin (via email notification)
**Goal**: Resolve payment failure

### Steps

1. Payment fails on renewal
2. Admin receives email notification
3. Admin clicks link to update payment
4. Admin adds new payment method
5. Payment retried automatically
6. Subscription restored

### Payment Failed Email

```
┌─────────────────────────────────────────────────────────────┐
│  Subject: Action Required: Payment Failed                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Hi John,                                                   │
│                                                             │
│  We were unable to process your payment of $299.00 for     │
│  your Stratum AI Growth subscription.                       │
│                                                             │
│  Reason: Card declined (insufficient funds)                 │
│                                                             │
│  To avoid service interruption, please update your         │
│  payment method within the next 3 days.                    │
│                                                             │
│              [Update Payment Method]                        │
│                                                             │
│  If you have any questions, our support team is here       │
│  to help.                                                   │
│                                                             │
│  - The Stratum AI Team                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Flow 9: Apply Coupon Code

**Actor**: Tenant Admin
**Goal**: Apply discount coupon

### Steps

1. User navigates to checkout or billing
2. User enters coupon code
3. Discount validated and displayed
4. Total updated with discount
5. Coupon applied to subscription

### Coupon Applied

```
┌─────────────────────────────────────────────────────────────┐
│  Order Summary                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Growth Plan (Monthly)                          $299.00    │
│                                                             │
│  Coupon Code                                                │
│  ┌────────────────────────────┐                            │
│  │ WELCOME20 ✓             [Apply]                         │
│  └────────────────────────────┘                            │
│  20% off first 3 months                                    │
│                                                             │
│  Discount (20% off)                            -$59.80     │
│  ────────────────────────────────────────────────────      │
│  Total Due Today                                $239.20    │
│                                                             │
│  Then $299.00/month after 3 months                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- [Specification](./spec.md) - Data models and architecture
- [API Contracts](./api-contracts.md) - API endpoints and schemas
- [Edge Cases](./edge-cases.md) - Error handling and edge cases

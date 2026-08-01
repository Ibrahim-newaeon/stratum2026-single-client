import type { Page } from '@playwright/test'

/**
 * Seed an authenticated session the way the app actually reads it.
 *
 * AuthContext restores a session from `localStorage['stratum_auth']` (a full
 * User object validated for id/email/role) on mount — no backend call. The old
 * E2E suite set `auth_token`/`user`, which the app ignores, so every protected
 * page redirected to /login. Set the correct key here.
 */
export interface E2EUser {
  id: string
  email: string
  name: string
  role: 'owner' | 'admin' | 'manager' | 'analyst' | 'viewer'
  organization?: string
  permissions: string[]
  /** Client ID for portal (VIEWER) users */
  client_id?: number | null
  user_type?: 'agency' | 'portal'
}

export const DEFAULT_USER: E2EUser = {
  id: 'e2e-admin-1',
  email: 'e2e@stratum.test',
  name: 'E2E Admin',
  role: 'admin',
  organization: 'E2E Org',
  permissions: ['all'],
  user_type: 'agency',
}

/**
 * Install the session before any app code runs (addInitScript runs on every
 * navigation/reload), so AuthContext sees it on first mount.
 *
 * Also satisfies OnboardingGuard, which wraps every /dashboard/* route. The
 * guard calls GET /onboarding/check and renders a full-screen spinner while
 * `isLoading` is true. There is no backend in the E2E harness, so that query
 * never settles, the spinner never goes away, and every assertion against
 * dashboard content times out — which is exactly how this suite failed: the
 * /dashboard/* specs (dashboard, emq, mobile, settings-flow, whatsapp-contacts)
 * all failed while /console, /login and the onboarding specs passed, because
 * only the dashboard tree is wrapped in the guard.
 *
 * The route is fulfilled with `required: false` rather than setting the
 * guard's `stratum_onboarding_skipped` escape hatch, so tests exercise the
 * real path — query resolves, guard renders children — instead of a bypass
 * branch that production users do not take.
 */
export async function authenticate(page: Page, user: E2EUser = DEFAULT_USER): Promise<void> {
  await page.addInitScript((u) => {
    localStorage.setItem('stratum_auth', JSON.stringify(u))
    // A non-expired-looking placeholder; the app does not verify it against a
    // backend for session restore, but some code reads it for API headers.
    sessionStorage.setItem('access_token', 'e2e.placeholder.token')
  }, user)

  await mockOnboardingCheck(page)
}

/**
 * Resolve OnboardingGuard's readiness probe as "nothing to do".
 *
 * Registered separately so a spec that deliberately drives the onboarding flow
 * can opt out by not calling `authenticate`.
 */
export async function mockOnboardingCheck(page: Page): Promise<void> {
  await page.route('**/onboarding/check**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: { required: false, redirect_to: null },
      }),
    })
  )
}

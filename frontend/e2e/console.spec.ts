import { test, expect } from '@playwright/test'
import { authenticate, DEFAULT_USER } from './utils/session'

const OWNER_USER = {
  ...DEFAULT_USER,
  id: 'e2e-owner-1',
  email: 'e2e-owner@stratum.test',
  name: 'E2E Owner',
  role: 'owner' as const,
}

test.describe('Console (owner ops shell)', () => {
  test.describe('as owner', () => {
    test.beforeEach(async ({ page }) => {
      await authenticate(page, OWNER_USER)
      await page.goto('/console')
    })

    test('should render the console shell', async ({ page }) => {
      await expect(page).toHaveURL(/\/console/)
      // Console sidebar groups (consoleNav.ts): Platform / Operations / Health
      await expect(page.getByText('Platform', { exact: true }).first()).toBeVisible({
        timeout: 15000,
      })
      await expect(page.getByRole('link', { name: /^Feature Flags$/i }).first()).toBeVisible()
    })

    test('should navigate between console pages', async ({ page, isMobile }) => {
      // Desktop sidebar navigation; collapsed behind a menu on mobile.
      test.skip(isMobile, 'desktop sidebar nav; mobile covered by mobile.spec.ts')
      await page.getByRole('link', { name: /^Feature Flags$/i }).first().click()
      await expect(page).toHaveURL(/\/console\/feature-flags/)

      await page.getByRole('link', { name: /^Users$/i }).first().click()
      await expect(page).toHaveURL(/\/console\/users/)
    })

    test('legacy /dashboard/superadmin/* redirects into /console/*', async ({ page }) => {
      await page.goto('/dashboard/superadmin/users')
      await expect(page).toHaveURL(/\/console\/users/, { timeout: 15000 })
    })
  })

  test.describe('as non-owner', () => {
    test('admin is denied console access', async ({ page }) => {
      await authenticate(page) // DEFAULT_USER is role: admin
      await page.goto('/console')
      // ProtectedRoute requiredRole="owner" bounces non-owners.
      await expect(page).toHaveURL(/unauthorized|login|dashboard/, { timeout: 15000 })
      await expect(page.getByRole('link', { name: /^Feature Flags$/i })).toHaveCount(0)
    })
  })
})

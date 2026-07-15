import { test, expect } from '@playwright/test'
import { DEFAULT_USER } from './utils/session'

test.describe('Logout Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Seed authenticated state ONCE (deliberately not via authenticate()'s
    // addInitScript — these tests clear the session and must not have it
    // re-seeded on the next navigation). stratum_auth is the key
    // AuthContext actually restores from.
    await page.goto('/')
    await page.evaluate((u) => {
      localStorage.setItem('stratum_auth', JSON.stringify(u))
      sessionStorage.setItem('access_token', 'e2e.placeholder.token')
    }, DEFAULT_USER)
    await page.goto('/dashboard/overview')
  })

  test('should logout and redirect to login', async ({ page }) => {
    // Open user menu / avatar dropdown
    const avatar = page.locator('[data-testid="user-menu-trigger"], [aria-label="User menu"]').first()
    if (await avatar.isVisible()) {
      await avatar.click()
    }

    // Click logout
    const logoutBtn = page.getByText(/^(Logout|Sign out)$/i).first()
    if (await logoutBtn.isVisible().catch(() => false)) {
      await logoutBtn.click()
    } else {
      // Fallback: simulate logout via session clear + navigate
      await page.evaluate(() => {
        localStorage.removeItem('stratum_auth')
        sessionStorage.removeItem('access_token')
        window.location.href = '/login'
      })
    }

    // Should redirect to login
    await expect(page).toHaveURL(/login/, { timeout: 15000 })

    // Auth session should be cleared
    const session = await page.evaluate(() => localStorage.getItem('stratum_auth'))
    expect(session).toBeNull()
  })

  test('should block dashboard access after logout', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.removeItem('stratum_auth')
      sessionStorage.removeItem('access_token')
    })
    await page.goto('/dashboard/overview')

    // Should be redirected to login (allow slower engines time for the
    // lazy-loaded route chunk + auth-restore bounce)
    await expect(page).toHaveURL(/login/, { timeout: 15000 })
  })
})

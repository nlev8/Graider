/**
 * App.jsx Decomposition — E2E flow tests
 *
 * Prerequisites: server at localhost:3000 in dev mode (FLASK_ENV=development,
 * auto-authenticates as local-dev teacher).
 *
 * These exercise the surfaces extracted during the App.jsx decomposition
 * (HelpTab, Sidebar, the Settings billing sub-tab / useSubscription hook, the
 * Script Builder tab, and full Sidebar navigation) in the LIVE app — the
 * end-to-end safety net complementing the per-slice unit/characterization tests.
 */
import { test, expect } from '@playwright/test'

const SIDEBAR_TABS = ['Grade', 'Results', 'Grading Setup', 'Analytics', 'Planner', 'Script Builder', 'Assistant', 'Settings', 'Help']

test.describe('App.jsx decomposition — Sidebar navigation (every extracted tab)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  for (const label of SIDEBAR_TABS) {
    test(`Sidebar navigates to "${label}" and renders without error`, async ({ page }) => {
      const tab = page.locator(`nav >> text=${label}`).first()
      const anyTab = (await tab.count()) ? tab : page.locator(`text=${label}`).first()
      await anyTab.click()
      await page.waitForTimeout(400)
      const body = await page.textContent('body')
      expect(body).not.toContain('Something went wrong') // no error boundary
      expect(body.length).toBeGreaterThan(100)
    })
  }
})

test.describe('App.jsx decomposition — HelpTab (slice 1)', () => {
  test('Help tab renders the extracted HelpTab content', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.locator('text=Help').first().click()
    await page.waitForTimeout(600)
    const body = await page.textContent('body')
    // HelpTab renders the Interactive Tutorial + Report-a-Bug cards
    expect(body).toMatch(/Interactive Tutorial|Found a Bug|Replay Tutorial/)
    expect(body).not.toContain('Something went wrong')
  })
})

test.describe('App.jsx decomposition — Sidebar collapse (slice 6)', () => {
  test('collapse toggle actually collapses and expands the sidebar', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const sidebar = page.getByTestId('sidebar')
    const toggle = page.getByTestId('sidebar-collapse-toggle')
    await expect(sidebar).toHaveCSS('width', '260px') // expanded by default
    await toggle.click()
    await expect(sidebar).toHaveCSS('width', '70px')  // collapsed
    await toggle.click()
    await expect(sidebar).toHaveCSS('width', '260px') // expanded again
    expect(await page.textContent('body')).not.toContain('Something went wrong')
  })
})

test.describe('App.jsx decomposition — Settings Billing / useSubscription (slices 3 + 7)', () => {
  test('Settings → Billing sub-tab renders (exercises useSubscription load)', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.locator('text=Settings').first().click()
    await page.waitForTimeout(400)
    // Dev-mode local teacher is not a Clever user, so the Billing sub-tab renders.
    const billing = page.locator('text=Billing').first()
    await expect(billing).toBeVisible()
    await billing.click()
    // useSubscription fires api.getSubscriptionStatus on billing select; allow it to settle
    await page.waitForTimeout(800)
    const body = await page.textContent('body')
    expect(body).not.toContain('Something went wrong')
    expect(body).toMatch(/Subscription|Billing|Plan|Usage/i)
  })
})

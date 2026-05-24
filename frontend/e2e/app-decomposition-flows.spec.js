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
  test('collapse toggle works without crashing', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    // The collapse toggle is the first button in the sidebar nav region.
    const toggle = page.locator('nav button').first()
    if (await toggle.count()) {
      await toggle.click()
      await page.waitForTimeout(300)
      // App still alive + tabs still navigable after collapse
      const body = await page.textContent('body')
      expect(body).not.toContain('Something went wrong')
      await page.locator('text=Help').first().click()
      await page.waitForTimeout(300)
      expect((await page.textContent('body'))).not.toContain('Something went wrong')
    }
  })
})

test.describe('App.jsx decomposition — Settings Billing / useSubscription (slices 3 + 7)', () => {
  test('Settings → Billing sub-tab renders (exercises useSubscription load)', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.locator('text=Settings').first().click()
    await page.waitForTimeout(400)
    const billing = page.locator('text=Billing').first()
    if (await billing.count()) {
      await billing.click()
      // useSubscription fires api.getSubscriptionStatus on billing select; allow it to settle
      await page.waitForTimeout(800)
      const body = await page.textContent('body')
      expect(body).not.toContain('Something went wrong')
      expect(body).toMatch(/Subscription|Billing|Plan|Usage/i)
    }
  })
})

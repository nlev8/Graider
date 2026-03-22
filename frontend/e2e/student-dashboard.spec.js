/**
 * Student Dashboard (Authenticated / Clever Path) Smoke Tests
 *
 * Tests the /student route which is the Clever SSO entry point.
 */
import { test, expect } from '@playwright/test'

test.describe('Student Dashboard — /student route', () => {

  test('/student renders without crashing', async ({ page }) => {
    await page.goto('/student')
    await page.waitForLoadState('networkidle')
    const body = await page.textContent('body')
    // Should show login form or dashboard — not a crash
    expect(body.length).toBeGreaterThan(0)
    expect(body).not.toContain('Something went wrong')
  })

  test('/student shows login or class code form', async ({ page }) => {
    await page.goto('/student')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    // Should have input fields for email/class code or show a dashboard
    const inputs = page.locator('input')
    const count = await inputs.count()
    // Either has login inputs or is showing the dashboard
    const body = await page.textContent('body')
    const hasLoginOrDashboard = count > 0 || body.includes('Dashboard') || body.includes('Log Out')
    expect(hasLoginOrDashboard).toBeTruthy()
  })
})

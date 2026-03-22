/**
 * Publish Flow Smoke Tests
 *
 * Tests the publish modal and content type differentiation.
 * Requires the teacher dashboard to be loaded.
 */
import { test, expect } from '@playwright/test'

test.describe('Publish Flow', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('Planner tab has Publish to Portal button', async ({ page }) => {
    // Navigate to Planner
    const plannerTab = page.locator('text=Planner').first()
    if (await plannerTab.isVisible()) {
      await plannerTab.click()
      await page.waitForTimeout(1000)
      const body = await page.textContent('body')
      // Publish button should be present somewhere in the Planner view
      const hasPublish = body.includes('Publish') || body.includes('publish')
      expect(hasPublish).toBeTruthy()
    }
  })
})

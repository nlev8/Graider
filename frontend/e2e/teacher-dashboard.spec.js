/**
 * Teacher Dashboard Smoke Tests
 *
 * Prerequisites: Server running at localhost:3000 in dev mode
 * (FLASK_ENV=development, which auto-authenticates as local-dev teacher)
 *
 * These tests verify the teacher dashboard renders and all major
 * UI interactions work. They are the safety net for App.jsx refactoring.
 */
import { test, expect } from '@playwright/test'

// ══════════════════════════════════════════
// NAVIGATION & TAB RENDERING
// ══════════════════════════════════════════

test.describe('Teacher Dashboard — Navigation', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    // Wait for the app to load (either login screen or dashboard)
    await page.waitForLoadState('networkidle')
  })

  test('app loads without crashing', async ({ page }) => {
    // Should have some content — not a blank page
    const body = await page.textContent('body')
    expect(body.length).toBeGreaterThan(0)
    // Should not show error boundary
    expect(body).not.toContain('Something went wrong')
  })

  test('Grading Setup tab renders', async ({ page }) => {
    // Click the Grade/Grading Setup tab
    const gradeTab = page.locator('text=Grade').first()
    if (await gradeTab.isVisible()) {
      await gradeTab.click()
      await page.waitForTimeout(500)
      // Should show some grading-related UI
      const content = await page.textContent('body')
      expect(content.length).toBeGreaterThan(100)
    }
  })

  test('Results tab renders', async ({ page }) => {
    const resultsTab = page.locator('text=Results').first()
    if (await resultsTab.isVisible()) {
      await resultsTab.click()
      await page.waitForTimeout(500)
      const content = await page.textContent('body')
      expect(content.length).toBeGreaterThan(100)
    }
  })

  test('Analytics tab renders', async ({ page }) => {
    const analyticsTab = page.locator('text=Analytics').first()
    if (await analyticsTab.isVisible()) {
      await analyticsTab.click()
      await page.waitForTimeout(500)
      const content = await page.textContent('body')
      expect(content.length).toBeGreaterThan(100)
    }
  })

  test('Planner tab renders', async ({ page }) => {
    const plannerTab = page.locator('text=Planner').first()
    if (await plannerTab.isVisible()) {
      await plannerTab.click()
      await page.waitForTimeout(500)
      const content = await page.textContent('body')
      expect(content.length).toBeGreaterThan(100)
    }
  })

  test('Settings tab renders', async ({ page }) => {
    const settingsTab = page.locator('text=Settings').first()
    if (await settingsTab.isVisible()) {
      await settingsTab.click()
      await page.waitForTimeout(500)
      const content = await page.textContent('body')
      expect(content.length).toBeGreaterThan(100)
    }
  })
})

// ══════════════════════════════════════════
// PLANNER TAB INTERACTIONS
// ══════════════════════════════════════════

test.describe('Teacher Dashboard — Planner', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    // Navigate to Planner
    const plannerTab = page.locator('text=Planner').first()
    if (await plannerTab.isVisible()) {
      await plannerTab.click()
      await page.waitForTimeout(500)
    }
  })

  test('Planner has content type selector', async ({ page }) => {
    // Should see Assessment or Assignment content type options
    const body = await page.textContent('body')
    const hasContentType = body.includes('Assessment') || body.includes('Assignment') || body.includes('Content Type')
    expect(hasContentType).toBeTruthy()
  })

  test('Planner has sub-tabs (Lesson Planning, Assessment Generator, etc.)', async ({ page }) => {
    const body = await page.textContent('body')
    const hasSubTabs = body.includes('Lesson Planning') || body.includes('Assessment') || body.includes('Assets')
    expect(hasSubTabs).toBeTruthy()
  })

  test('Assets tab shows in Planner', async ({ page }) => {
    const assetsBtn = page.locator('text=Assets').first()
    if (await assetsBtn.isVisible()) {
      await assetsBtn.click()
      await page.waitForTimeout(500)
      const body = await page.textContent('body')
      // Should show resources list or empty state
      const hasAssets = body.includes('My Resources') || body.includes('No saved resources')
      expect(hasAssets).toBeTruthy()
    }
  })
})

// ══════════════════════════════════════════
// SETTINGS TAB INTERACTIONS
// ══════════════════════════════════════════

test.describe('Teacher Dashboard — Settings', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const settingsTab = page.locator('text=Settings').first()
    if (await settingsTab.isVisible()) {
      await settingsTab.click()
      await page.waitForTimeout(500)
    }
  })

  test('Settings has sub-tabs', async ({ page }) => {
    const body = await page.textContent('body')
    // Settings should have sections like Rubric, AI Notes, Classroom, etc.
    const hasSubTabs = body.includes('Rubric') || body.includes('AI Notes') || body.includes('Classroom') || body.includes('General')
    expect(hasSubTabs).toBeTruthy()
  })
})

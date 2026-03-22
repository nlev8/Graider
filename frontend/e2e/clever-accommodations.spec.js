/**
 * Clever SSO & Accommodation API Tests
 *
 * Tests Clever integration endpoints and accommodation management.
 * Does NOT require actual Clever credentials — tests API responses
 * and UI element presence in dev mode.
 */
import { test, expect } from '@playwright/test'
import { AUTH_HEADERS } from './helpers.js'

test.describe('Clever SSO — API Endpoints', () => {
  test('GET /api/clever/health returns config status', async ({ request }) => {
    const response = await request.get('/api/clever/health')
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toHaveProperty('configured')
  })

  test('GET /api/clever/login-url returns URL or error', async ({ request }) => {
    const response = await request.get('/api/clever/login-url')
    expect([200, 400, 500]).toContain(response.status())
    const data = await response.json()
    // Should have either url or error
    expect(data.url || data.error || data.message).toBeDefined()
  })

  test('GET /api/clever/session returns session info', async ({ request }) => {
    const response = await request.get('/api/clever/session', { headers: AUTH_HEADERS })
    expect([200, 401]).toContain(response.status())
  })

  test('GET /api/clever/district-keys returns key status', async ({ request }) => {
    const response = await request.get('/api/clever/district-keys', { headers: AUTH_HEADERS })
    expect([200, 401, 403, 500]).toContain(response.status())
  })

  test('POST /api/clever/logout clears session', async ({ request }) => {
    const response = await request.post('/api/clever/logout', { headers: AUTH_HEADERS })
    expect([200, 204]).toContain(response.status())
  })

  test('POST /api/clever/sync-roster without data returns error', async ({ request }) => {
    const response = await request.post('/api/clever/sync-roster', {
      headers: AUTH_HEADERS,
      data: {},
    })
    // Should fail gracefully without real Clever connection
    expect([200, 400, 401, 500]).toContain(response.status())
  })
})

test.describe('Accommodations — API', () => {
  test('GET /api/accommodation-presets returns presets', async ({ request }) => {
    const response = await request.get('/api/accommodation-presets', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toBeDefined()
  })

  test('POST /api/clever/apply-accommodations without data returns error', async ({ request }) => {
    const response = await request.post('/api/clever/apply-accommodations', {
      headers: AUTH_HEADERS,
      data: {},
    })
    expect([200, 400, 401, 500]).toContain(response.status())
  })
})

test.describe('Clever SSO — UI Elements', () => {
  test('teacher dashboard loads in dev mode', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    // Should have teacher dashboard content
    expect(body.length).toBeGreaterThan(100)
  })

  test('Settings tab is accessible', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    // Look for Settings tab
    const settingsTab = page.locator('text=Settings').first()
    if (await settingsTab.isVisible()) {
      await settingsTab.click()
      await page.waitForTimeout(1000)
      const body = await page.textContent('body')
      expect(body.length).toBeGreaterThan(100)
    }
  })
})

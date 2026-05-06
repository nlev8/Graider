/**
 * Health Check & API Smoke Tests
 *
 * Verifies the server is running and key API endpoints respond.
 */
import { test, expect } from '@playwright/test'

test.describe('Server Health', () => {

  test('/healthz returns ok', async ({ request }) => {
    const response = await request.get('/healthz')
    // Per fail-closed contract (PR #220): 503 when any required dep is in
    // error/degraded state, 200 when all are ok or not-configured.
    // Body shape is preserved either way.
    expect([200, 503]).toContain(response.status())
    const data = await response.json()
    expect(data.app).toBe('ok')
    if (response.status() === 200) {
      // Healthy path — every reported dep should be in the healthy whitelist.
      const healthyStates = ['ok', 'not configured']
      for (const dep of ['supabase', 'redis']) {
        if (data[dep] !== undefined) {
          expect(healthyStates).toContain(data[dep])
        }
      }
    }
  })

  test('/api/clever/health returns status', async ({ request }) => {
    const response = await request.get('/api/clever/health')
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toHaveProperty('configured')
    expect(data).toHaveProperty('supabase_available')
  })

  test('/ serves the React app', async ({ request }) => {
    const response = await request.get('/')
    expect(response.status()).toBe(200)
    const html = await response.text()
    expect(html.toLowerCase()).toContain('<!doctype html>')
  })

  test('/join serves the React app', async ({ request }) => {
    const response = await request.get('/join')
    expect(response.status()).toBe(200)
    const html = await response.text()
    expect(html.toLowerCase()).toContain('<!doctype html>')
  })

  test('/student serves the React app', async ({ request }) => {
    const response = await request.get('/student')
    expect(response.status()).toBe(200)
    const html = await response.text()
    expect(html.toLowerCase()).toContain('<!doctype html>')
  })

  test('/api/user-manual responds', async ({ request }) => {
    const response = await request.get('/api/user-manual')
    // Should return 200 with content or 404 if no manual file
    expect([200, 404]).toContain(response.status())
  })
})

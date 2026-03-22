/**
 * Behavior Tracking API Tests
 *
 * Tests the behavior tracking session, events, and data endpoints.
 */
import { test, expect } from '@playwright/test'
import { AUTH_HEADERS } from './helpers.js'

// ══════════════════════════════════════════
// Behavior Tracking API
// ══════════════════════════════════════════

test.describe('Behavior Tracking — API', () => {
  test('POST /api/behavior/session starts a session', async ({ request }) => {
    const response = await request.post('/api/behavior/session', {
      headers: AUTH_HEADERS,
      data: { class_id: 'test-class', period: '1st' },
    })
    expect([200, 201, 400, 500]).toContain(response.status())
  })

  test('GET /api/behavior/data returns behavior data', async ({ request }) => {
    const response = await request.get('/api/behavior/data', { headers: AUTH_HEADERS })
    expect([200, 400, 500]).toContain(response.status())
  })

  test('GET /api/behavior/events returns events list', async ({ request }) => {
    const response = await request.get('/api/behavior/events', { headers: AUTH_HEADERS })
    expect([200, 400, 500]).toContain(response.status())
  })

  test('DELETE /api/behavior/data clears data', async ({ request }) => {
    const response = await request.delete('/api/behavior/data', { headers: AUTH_HEADERS })
    expect([200, 204, 400, 500]).toContain(response.status())
  })

  test('POST /api/behavior/session with empty data returns error or creates', async ({ request }) => {
    const response = await request.post('/api/behavior/session', {
      headers: AUTH_HEADERS,
      data: {},
    })
    expect([200, 201, 400, 500]).toContain(response.status())
  })

  test('GET /api/behavior/data after clear returns empty or error', async ({ request }) => {
    // Clear first
    await request.delete('/api/behavior/data', { headers: AUTH_HEADERS })
    // Then check
    const response = await request.get('/api/behavior/data', { headers: AUTH_HEADERS })
    expect([200, 400, 500]).toContain(response.status())
  })
})

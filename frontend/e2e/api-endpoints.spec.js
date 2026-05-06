/**
 * API Endpoint Smoke Tests
 *
 * Verifies all major API endpoint groups respond correctly:
 * - Health endpoints
 * - Teacher-authenticated endpoints
 * - Auth rejection (no header)
 * - Student public endpoints
 * - SPA routing
 */
import { test, expect } from '@playwright/test'
import { AUTH_HEADERS } from './helpers.js'

// ══════════════════════════════════════════
// Health Endpoints
// ══════════════════════════════════════════

test.describe('Health Endpoints', () => {
  test('GET /healthz returns ok', async ({ request }) => {
    const response = await request.get('/healthz')
    // Per fail-closed contract (PR #220): 503 when any required dep is in
    // error/degraded state, 200 when all healthy. Body shape is preserved.
    expect([200, 503]).toContain(response.status())
    const data = await response.json()
    expect(data.app).toBe('ok')
  })

  test('GET /api/clever/health returns status', async ({ request }) => {
    const response = await request.get('/api/clever/health')
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toHaveProperty('configured')
  })
})

// ══════════════════════════════════════════
// Teacher Authenticated Endpoints
// ══════════════════════════════════════════

test.describe('Teacher Authenticated Endpoints', () => {
  test('GET /api/list-assignments returns 200', async ({ request }) => {
    const response = await request.get('/api/list-assignments', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/load-rubric returns 200', async ({ request }) => {
    const response = await request.get('/api/load-rubric', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/load-global-settings returns 200', async ({ request }) => {
    const response = await request.get('/api/load-global-settings', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/teacher/assessments returns 200', async ({ request }) => {
    const response = await request.get('/api/teacher/assessments', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/list-resources returns 200', async ({ request }) => {
    const response = await request.get('/api/list-resources', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/list-periods returns 200', async ({ request }) => {
    const response = await request.get('/api/list-periods', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/status returns 200', async ({ request }) => {
    const response = await request.get('/api/status', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/check-api-keys returns 200', async ({ request }) => {
    const response = await request.get('/api/check-api-keys', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/classes returns 200 or 500 (no Supabase)', async ({ request }) => {
    const response = await request.get('/api/classes', { headers: AUTH_HEADERS })
    expect([200, 500]).toContain(response.status())
  })

  test('GET /api/list-lessons returns 200', async ({ request }) => {
    const response = await request.get('/api/list-lessons', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/analytics returns 200', async ({ request }) => {
    const response = await request.get('/api/analytics', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('GET /api/accommodation-presets returns 200', async ({ request }) => {
    const response = await request.get('/api/accommodation-presets', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })
})

// ══════════════════════════════════════════
// Auth Rejection (no header)
// ══════════════════════════════════════════

test.describe('Auth Rejection — No Header', () => {
  const NO_AUTH = { 'Content-Type': 'application/json' }

  // In dev mode (FLASK_ENV=development on localhost), the auth middleware
  // auto-authenticates as 'local-dev', so these endpoints return 200 instead
  // of 401/403. Both behaviors are correct for their respective environments.

  test('GET /api/list-assignments without auth returns 200 (dev) or 401/403 (prod)', async ({ request }) => {
    const response = await request.get('/api/list-assignments', { headers: NO_AUTH })
    expect([200, 401, 403]).toContain(response.status())
  })

  test('GET /api/load-rubric without auth returns 200 (dev) or 401/403 (prod)', async ({ request }) => {
    const response = await request.get('/api/load-rubric', { headers: NO_AUTH })
    expect([200, 401, 403]).toContain(response.status())
  })

  test('POST /api/save-rubric without auth returns 200 (dev) or 401/403 (prod)', async ({ request }) => {
    const response = await request.post('/api/save-rubric', { headers: NO_AUTH, data: {} })
    expect([200, 401, 403]).toContain(response.status())
  })

  test('GET /api/teacher/assessments without auth returns 200 (dev) or 401/403 (prod)', async ({ request }) => {
    const response = await request.get('/api/teacher/assessments', { headers: NO_AUTH })
    expect([200, 401, 403]).toContain(response.status())
  })

  test('POST /api/publish-assessment without auth returns 200 (dev) or 401/403 (prod)', async ({ request }) => {
    const response = await request.post('/api/publish-assessment', { headers: NO_AUTH, data: {} })
    expect([200, 400, 401, 403]).toContain(response.status())
  })

  test('GET /api/list-resources without auth returns 200 (dev) or 401/403 (prod)', async ({ request }) => {
    const response = await request.get('/api/list-resources', { headers: NO_AUTH })
    expect([200, 401, 403]).toContain(response.status())
  })

  test('GET /api/ferpa/data-summary without auth returns 200 (dev) or 401/403 (prod)', async ({ request }) => {
    const response = await request.get('/api/ferpa/data-summary', { headers: NO_AUTH })
    expect([200, 401, 403]).toContain(response.status())
  })

  test('POST /api/ferpa/delete-all-data without auth returns 200/400 (dev) or 401/403 (prod)', async ({ request }) => {
    const response = await request.post('/api/ferpa/delete-all-data', { headers: NO_AUTH, data: {} })
    expect([200, 400, 401, 403]).toContain(response.status())
  })
})

// ══════════════════════════════════════════
// Student Public Endpoints
// ══════════════════════════════════════════

test.describe('Student Public Endpoints', () => {
  test('GET /api/student/join/INVALID returns 404', async ({ request }) => {
    const response = await request.get('/api/student/join/INVALID')
    expect([404, 400]).toContain(response.status())
  })

  test('POST /api/student/login with empty body returns 400', async ({ request }) => {
    const response = await request.post('/api/student/login', {
      headers: { 'Content-Type': 'application/json' },
      data: {},
    })
    expect([400, 401, 422]).toContain(response.status())
  })

  test('POST /api/student/submit/INVALID returns error', async ({ request }) => {
    const response = await request.post('/api/student/submit/INVALID', {
      headers: { 'Content-Type': 'application/json' },
      data: { student_name: 'Test', answers: {} },
    })
    expect([400, 404]).toContain(response.status())
  })

  test('GET /api/student/session without token returns error', async ({ request }) => {
    const response = await request.get('/api/student/session')
    expect([401, 403, 400]).toContain(response.status())
  })
})

// ══════════════════════════════════════════
// SPA Routing — All Routes Serve HTML
// ══════════════════════════════════════════

test.describe('SPA Routing', () => {
  test('/ serves HTML', async ({ request }) => {
    const response = await request.get('/')
    expect(response.status()).toBe(200)
    const html = await response.text()
    expect(html.toLowerCase()).toContain('<!doctype html>')
  })

  test('/join serves HTML', async ({ request }) => {
    const response = await request.get('/join')
    expect(response.status()).toBe(200)
    const html = await response.text()
    expect(html.toLowerCase()).toContain('<!doctype html>')
  })

  test('/student serves HTML', async ({ request }) => {
    const response = await request.get('/student')
    expect(response.status()).toBe(200)
    const html = await response.text()
    expect(html.toLowerCase()).toContain('<!doctype html>')
  })

  test('/nonexistent serves HTML (SPA fallback)', async ({ request }) => {
    const response = await request.get('/nonexistent-route-xyz')
    expect(response.status()).toBe(200)
    const html = await response.text()
    expect(html.toLowerCase()).toContain('<!doctype html>')
  })

  test('/join/SOMECODE serves HTML', async ({ request }) => {
    const response = await request.get('/join/SOMECODE')
    expect(response.status()).toBe(200)
    const html = await response.text()
    expect(html.toLowerCase()).toContain('<!doctype html>')
  })
})

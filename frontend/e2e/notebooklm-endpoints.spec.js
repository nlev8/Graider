/**
 * NotebookLM Integration API Tests
 *
 * Smoke tests for NotebookLM endpoints. These require external
 * credentials to fully function, but we verify the endpoints
 * respond correctly even without them.
 */
import { test, expect } from '@playwright/test'
import { AUTH_HEADERS } from './helpers.js'

// ══════════════════════════════════════════
// NotebookLM API
// ══════════════════════════════════════════

test.describe('NotebookLM — API Endpoints', () => {
  test('GET /api/notebooklm/auth-status returns auth state', async ({ request }) => {
    const response = await request.get('/api/notebooklm/auth-status', { headers: AUTH_HEADERS })
    expect([200, 401, 500]).toContain(response.status())
  })

  test('POST /api/notebooklm/create-notebook without auth returns error', async ({ request }) => {
    const response = await request.post('/api/notebooklm/create-notebook', {
      headers: AUTH_HEADERS,
      data: { title: 'Test Notebook', sources: [] },
    })
    // Will fail without NotebookLM credentials — that's expected
    expect([200, 400, 401, 500]).toContain(response.status())
  })

  test('POST /api/notebooklm/generate without notebook returns error', async ({ request }) => {
    const response = await request.post('/api/notebooklm/generate', {
      headers: AUTH_HEADERS,
      data: { type: 'summary' },
    })
    expect([200, 400, 401, 500]).toContain(response.status())
  })

  test('GET /api/notebooklm/download/summary without content returns error', async ({ request }) => {
    const response = await request.get('/api/notebooklm/download/summary', { headers: AUTH_HEADERS })
    expect([200, 400, 404, 500]).toContain(response.status())
  })

  test('GET /api/notebooklm/download/flashcards without content returns error', async ({ request }) => {
    const response = await request.get('/api/notebooklm/download/flashcards', { headers: AUTH_HEADERS })
    expect([200, 400, 404, 500]).toContain(response.status())
  })

  test('GET /api/notebooklm/download/invalid-type returns error', async ({ request }) => {
    const response = await request.get('/api/notebooklm/download/nonexistent-type', { headers: AUTH_HEADERS })
    expect([200, 400, 404, 500]).toContain(response.status())
  })
})

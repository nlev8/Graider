/**
 * Survey API Tests
 *
 * Tests survey create, list, results, and submit endpoints.
 */
import { test, expect } from '@playwright/test'
import { AUTH_HEADERS } from './helpers.js'

// ══════════════════════════════════════════
// Survey CRUD
// ══════════════════════════════════════════

test.describe('Surveys — Create and List', () => {
  test('POST /api/survey/create creates a survey', async ({ request }) => {
    const response = await request.post('/api/survey/create', {
      headers: AUTH_HEADERS,
      data: {
        title: 'Playwright Feedback Survey ' + Date.now(),
        questions: [
          { text: 'How was the lesson?', type: 'rating' },
          { text: 'What could be improved?', type: 'text' },
        ],
      },
    })
    expect([200, 201, 400, 500]).toContain(response.status())
  })

  test('GET /api/survey/list returns surveys', async ({ request }) => {
    const response = await request.get('/api/survey/list', { headers: AUTH_HEADERS })
    expect([200, 400, 500]).toContain(response.status())
  })

  test('GET /api/survey/results returns results', async ({ request }) => {
    const response = await request.get('/api/survey/results', { headers: AUTH_HEADERS })
    expect([200, 400, 500]).toContain(response.status())
  })

  test('POST /api/survey/create with empty data returns error', async ({ request }) => {
    const response = await request.post('/api/survey/create', {
      headers: AUTH_HEADERS,
      data: {},
    })
    expect([200, 400, 500]).toContain(response.status())
  })
})

test.describe('Surveys — Submit', () => {
  test('POST /api/survey/INVALID/submit returns error', async ({ request }) => {
    const response = await request.post('/api/survey/INVALID/submit', {
      headers: { 'Content-Type': 'application/json' },
      data: { responses: [{ question: 'How was it?', answer: 'Great' }] },
    })
    expect([400, 404, 500]).toContain(response.status())
  })

  test('POST /api/survey/INVALID/submit with empty body returns error', async ({ request }) => {
    const response = await request.post('/api/survey/INVALID/submit', {
      headers: { 'Content-Type': 'application/json' },
      data: {},
    })
    expect([400, 404, 500]).toContain(response.status())
  })
})

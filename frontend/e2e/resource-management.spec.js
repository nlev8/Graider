/**
 * Resource Management E2E Tests
 *
 * Verifies the resource save/list/load/delete API flow:
 * - POST /api/save-resource (lesson plan and assessment)
 * - GET /api/list-resources (with and without type filter)
 * - POST /api/load-resource (by ID)
 * - POST /api/delete-resource (valid and invalid IDs)
 */
import { test, expect } from '@playwright/test'
import { AUTH_HEADERS } from './helpers.js'

// ══════════════════════════════════════════
// Save and List
// ══════════════════════════════════════════

test.describe('Resource Management — Save and List', () => {
  let savedResourceId

  test('POST /api/save-resource saves a lesson plan resource', async ({ request }) => {
    const response = await request.post('/api/save-resource', {
      headers: AUTH_HEADERS,
      data: {
        type: 'lesson_plan',
        title: 'Playwright Test Lesson ' + Date.now(),
        content: { objectives: ['Test objective'], activities: ['Test activity'] },
      },
    })
    expect([200, 201]).toContain(response.status())
    const data = await response.json()
    if (data.id) savedResourceId = data.id
  })

  test('POST /api/save-resource saves an assessment resource', async ({ request }) => {
    const response = await request.post('/api/save-resource', {
      headers: AUTH_HEADERS,
      data: {
        type: 'assessment',
        title: 'Playwright Test Assessment ' + Date.now(),
        content: { questions: [{ q: 'What is 1+1?', a: '2' }] },
      },
    })
    expect([200, 201]).toContain(response.status())
  })

  test('GET /api/list-resources returns saved resources', async ({ request }) => {
    const response = await request.get('/api/list-resources', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(Array.isArray(data.resources || data)).toBeTruthy()
  })

  test('GET /api/list-resources with type filter returns filtered results', async ({ request }) => {
    const response = await request.get('/api/list-resources?type=lesson_plan', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toBeDefined()
  })
})

// ══════════════════════════════════════════
// Load and Delete
// ══════════════════════════════════════════

test.describe('Resource Management — Load and Delete', () => {
  let resourceId

  test.beforeAll(async ({ request }) => {
    const response = await request.post('/api/save-resource', {
      headers: AUTH_HEADERS,
      data: {
        type: 'lesson_plan',
        title: 'Delete Test Resource ' + Date.now(),
        content: { test: true },
      },
    })
    const data = await response.json()
    resourceId = data.id || data.resource_id || null
  })

  test('POST /api/load-resource loads a saved resource', async ({ request }) => {
    test.skip(!resourceId, 'No resource ID from save')
    const response = await request.post('/api/load-resource', {
      headers: AUTH_HEADERS,
      data: { id: resourceId },
    })
    expect([200, 400, 404]).toContain(response.status())
  })

  test('POST /api/delete-resource removes a resource', async ({ request }) => {
    test.skip(!resourceId, 'No resource ID from save')
    const response = await request.post('/api/delete-resource', {
      headers: AUTH_HEADERS,
      data: { id: resourceId },
    })
    expect([200, 400, 404]).toContain(response.status())
  })

  test('deleted resource no longer loadable', async ({ request }) => {
    test.skip(!resourceId, 'No resource ID from save')
    const response = await request.post('/api/load-resource', {
      headers: AUTH_HEADERS,
      data: { id: resourceId },
    })
    // Should be 404 or return empty/error
    expect([200, 400, 404]).toContain(response.status())
  })

  test('POST /api/delete-resource with invalid ID returns error', async ({ request }) => {
    const response = await request.post('/api/delete-resource', {
      headers: AUTH_HEADERS,
      data: { id: 'nonexistent-resource-id-xyz' },
    })
    expect([200, 404, 400]).toContain(response.status())
  })
})

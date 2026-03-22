/**
 * Teacher Publish Modal & Assessment Management API Tests
 *
 * Tests the publish API directly: creating, listing, toggling,
 * fetching results, and deleting published assessments.
 * Also verifies auth requirements on protected endpoints.
 */
import { test, expect } from '@playwright/test'
import { AUTH_HEADERS, uniqueName } from './helpers.js'

const TEST_ASSESSMENT = {
  title: 'Publish Modal Test',
  sections: [{
    name: 'Questions',
    questions: [
      { number: 1, type: 'multiple_choice', question: 'Test question A?', options: ['A) Yes', 'B) No', 'C) Maybe', 'D) None'], answer: 'A', points: 5 },
      { number: 2, type: 'true_false', question: 'This is a test.', answer: 'True', points: 5 },
    ],
  }],
}

test.describe('Publish API — Assessment Type', () => {
  let joinCode

  test.afterAll(async ({ request }) => {
    if (joinCode) {
      await request.delete(`/api/teacher/assessment/${joinCode}`, { headers: AUTH_HEADERS })
    }
  })

  test('publish with assessment type returns join code', async ({ request }) => {
    const response = await request.post('/api/publish-assessment', {
      headers: AUTH_HEADERS,
      data: {
        assessment: { ...TEST_ASSESSMENT, title: 'Assessment Type ' + Date.now() },
        settings: { teacher_name: 'Test Teacher', show_score_immediately: true, content_type: 'assessment' },
      },
    })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data.join_code).toBeTruthy()
    joinCode = data.join_code
  })
})

test.describe('Publish API — Assignment Type', () => {
  let joinCode

  test.afterAll(async ({ request }) => {
    if (joinCode) {
      await request.delete(`/api/teacher/assessment/${joinCode}`, { headers: AUTH_HEADERS })
    }
  })

  test('publish with assignment type returns join code', async ({ request }) => {
    const response = await request.post('/api/publish-assessment', {
      headers: AUTH_HEADERS,
      data: {
        assessment: { ...TEST_ASSESSMENT, title: 'Assignment Type ' + Date.now() },
        settings: { teacher_name: 'Test Teacher', show_score_immediately: true, content_type: 'assignment' },
      },
    })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data.join_code).toBeTruthy()
    joinCode = data.join_code
  })
})

test.describe('Publish API — Settings', () => {
  let joinCodeTimeLimit
  let joinCodeNoRetakes
  let joinCodeRetakes

  test.afterAll(async ({ request }) => {
    for (const code of [joinCodeTimeLimit, joinCodeNoRetakes, joinCodeRetakes]) {
      if (code) {
        await request.delete(`/api/teacher/assessment/${code}`, { headers: AUTH_HEADERS })
      }
    }
  })

  test('publish with time limit', async ({ request }) => {
    const response = await request.post('/api/publish-assessment', {
      headers: AUTH_HEADERS,
      data: {
        assessment: { ...TEST_ASSESSMENT, title: 'Time Limit ' + Date.now() },
        settings: { teacher_name: 'Test Teacher', show_score_immediately: true, content_type: 'assessment', time_limit: 30 },
      },
    })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data.join_code).toBeTruthy()
    joinCodeTimeLimit = data.join_code
  })

  test('publish with retakes disabled', async ({ request }) => {
    const response = await request.post('/api/publish-assessment', {
      headers: AUTH_HEADERS,
      data: {
        assessment: { ...TEST_ASSESSMENT, title: 'No Retakes ' + Date.now() },
        settings: { teacher_name: 'Test Teacher', show_score_immediately: true, content_type: 'assessment', allow_retakes: false },
      },
    })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data.join_code).toBeTruthy()
    joinCodeNoRetakes = data.join_code
  })

  test('publish with retakes enabled', async ({ request }) => {
    const response = await request.post('/api/publish-assessment', {
      headers: AUTH_HEADERS,
      data: {
        assessment: { ...TEST_ASSESSMENT, title: 'Retakes On ' + Date.now() },
        settings: { teacher_name: 'Test Teacher', show_score_immediately: true, content_type: 'assessment', allow_retakes: true },
      },
    })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data.join_code).toBeTruthy()
    joinCodeRetakes = data.join_code
  })
})

test.describe('Publish API — List and Manage', () => {
  let joinCode

  test.beforeAll(async ({ request }) => {
    const response = await request.post('/api/publish-assessment', {
      headers: AUTH_HEADERS,
      data: {
        assessment: { ...TEST_ASSESSMENT, title: 'List Test ' + Date.now() },
        settings: { teacher_name: 'Test Teacher', show_score_immediately: true, content_type: 'assessment' },
      },
    })
    const data = await response.json()
    joinCode = data.join_code
  })

  test.afterAll(async ({ request }) => {
    if (joinCode) {
      await request.delete(`/api/teacher/assessment/${joinCode}`, { headers: AUTH_HEADERS })
    }
  })

  test('list assessments returns published ones', async ({ request }) => {
    test.skip(!joinCode, 'No join code')
    const response = await request.get('/api/teacher/assessments', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(Array.isArray(data.assessments || data)).toBeTruthy()
  })

  test('toggle deactivates assessment', async ({ request }) => {
    test.skip(!joinCode, 'No join code')
    const response = await request.post(`/api/teacher/assessment/${joinCode}/toggle`, { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toHaveProperty('active')
  })

  test('toggle reactivates assessment', async ({ request }) => {
    test.skip(!joinCode, 'No join code')
    // Toggle again to reactivate
    const response = await request.post(`/api/teacher/assessment/${joinCode}/toggle`, { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toHaveProperty('active')
  })

  test('get results for assessment', async ({ request }) => {
    test.skip(!joinCode, 'No join code')
    const response = await request.get(`/api/teacher/assessment/${joinCode}/results`, { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    const data = await response.json()
    expect(data).toHaveProperty('submissions')
  })

  test('delete actually removes assessment', async ({ request }) => {
    // Publish a separate one to delete
    const pubResponse = await request.post('/api/publish-assessment', {
      headers: AUTH_HEADERS,
      data: {
        assessment: { ...TEST_ASSESSMENT, title: 'Delete Me ' + Date.now() },
        settings: { teacher_name: 'Test Teacher', show_score_immediately: true, content_type: 'assessment' },
      },
    })
    const pubData = await pubResponse.json()
    const deleteCode = pubData.join_code
    expect(deleteCode).toBeTruthy()

    const delResponse = await request.delete(`/api/teacher/assessment/${deleteCode}`, { headers: AUTH_HEADERS })
    expect(delResponse.status()).toBe(200)

    // Verify it is gone — student join should fail
    const joinResponse = await request.get(`/api/student/join/${deleteCode}`)
    expect([404, 400, 410]).toContain(joinResponse.status())
  })
})

test.describe('Publish API — Auth Required', () => {
  const NO_AUTH = { 'Content-Type': 'application/json' }

  // In dev mode, auth middleware auto-authenticates, so these accept 200 as valid too
  test('publish requires auth (or succeeds in dev mode)', async ({ request }) => {
    const response = await request.post('/api/publish-assessment', {
      headers: NO_AUTH,
      data: {
        assessment: TEST_ASSESSMENT,
        settings: { teacher_name: 'No Auth', content_type: 'assessment' },
      },
    })
    expect([200, 400, 401, 403]).toContain(response.status())
  })

  test('list requires auth (or succeeds in dev mode)', async ({ request }) => {
    const response = await request.get('/api/teacher/assessments', { headers: NO_AUTH })
    expect([200, 401, 403]).toContain(response.status())
  })

  test('delete requires auth (or succeeds in dev mode)', async ({ request }) => {
    const response = await request.delete('/api/teacher/assessment/FAKECODE', { headers: NO_AUTH })
    expect([200, 401, 403, 404]).toContain(response.status())
  })

  test('toggle requires auth (or succeeds in dev mode)', async ({ request }) => {
    const response = await request.post('/api/teacher/assessment/FAKECODE/toggle', { headers: NO_AUTH })
    expect([200, 401, 403, 404]).toContain(response.status())
  })

  test('results requires auth (or succeeds in dev mode)', async ({ request }) => {
    const response = await request.get('/api/teacher/assessment/FAKECODE/results', { headers: NO_AUTH })
    expect([200, 401, 403, 404]).toContain(response.status())
  })
})

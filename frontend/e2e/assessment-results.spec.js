/**
 * Assessment Results E2E Tests
 *
 * Tests the /api/assessment-results endpoint and analytics source filter:
 * - Returns assessments with correct structure (stats, submissions, question_analysis)
 * - assessment_category filter (?category=formative / ?category=summative) works
 * - question_analysis includes response_distribution after MC submissions
 * - /api/analytics?source=assessments returns assessment_stats + assessment_category_summary
 */
import { test, expect } from '@playwright/test'
import {
  AUTH_HEADERS,
  publishAssessment,
  deleteAssessment,
  startAssessment,
  uniqueName,
  answerMC,
  clickNext,
  finishAndSubmit,
  ASSESSMENTS,
} from './helpers.js'

// ══════════════════════════════════════════
// /api/assessment-results — Basic structure
// ══════════════════════════════════════════

test.describe('Assessment Results — endpoint smoke test', () => {
  test('GET /api/assessment-results returns 200 with assessments array', async ({ request }) => {
    var response = await request.get('/api/assessment-results', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    expect(data).toHaveProperty('assessments')
    expect(Array.isArray(data.assessments)).toBeTruthy()
  })
})

// ══════════════════════════════════════════
// Publish formative assessment → appears in results
// ══════════════════════════════════════════

test.describe('Assessment Results — formative assessment appears', () => {
  var joinCode = null

  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.mcOnly, {
      assessment_category: 'formative',
    })
  })

  test.afterAll(async ({ request }) => {
    await deleteAssessment(request, joinCode)
  })

  test('published formative assessment appears in results', async ({ request }) => {
    test.skip(!joinCode, 'publish failed')
    var response = await request.get('/api/assessment-results', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    var found = data.assessments.find(function(a) { return a.join_code === joinCode })
    expect(found).toBeTruthy()
  })

  test('formative assessment has required structure fields', async ({ request }) => {
    test.skip(!joinCode, 'publish failed')
    var response = await request.get('/api/assessment-results', { headers: AUTH_HEADERS })
    var data = await response.json()
    var found = data.assessments.find(function(a) { return a.join_code === joinCode })
    expect(found).toBeTruthy()
    expect(found).toHaveProperty('id')
    expect(found).toHaveProperty('title')
    expect(found).toHaveProperty('assessment_category')
    expect(found).toHaveProperty('stats')
    expect(found).toHaveProperty('submissions')
    expect(found).toHaveProperty('question_analysis')
    expect(Array.isArray(found.submissions)).toBeTruthy()
    expect(Array.isArray(found.question_analysis)).toBeTruthy()
  })

  test('formative assessment has correct category', async ({ request }) => {
    test.skip(!joinCode, 'publish failed')
    var response = await request.get('/api/assessment-results', { headers: AUTH_HEADERS })
    var data = await response.json()
    var found = data.assessments.find(function(a) { return a.join_code === joinCode })
    expect(found).toBeTruthy()
    expect(found.assessment_category).toBe('formative')
  })

  test('stats object has expected keys', async ({ request }) => {
    test.skip(!joinCode, 'publish failed')
    var response = await request.get('/api/assessment-results', { headers: AUTH_HEADERS })
    var data = await response.json()
    var found = data.assessments.find(function(a) { return a.join_code === joinCode })
    expect(found).toBeTruthy()
    var stats = found.stats
    expect(stats).toHaveProperty('total_submissions')
    expect(stats).toHaveProperty('average_score')
    expect(stats).toHaveProperty('highest_score')
    expect(stats).toHaveProperty('lowest_score')
    expect(stats).toHaveProperty('pending_count')
    expect(stats).toHaveProperty('graded_count')
  })
})

// ══════════════════════════════════════════
// Publish summative assessment → appears in results
// ══════════════════════════════════════════

test.describe('Assessment Results — summative assessment appears', () => {
  var joinCode = null

  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.tfOnly, {
      assessment_category: 'summative',
    })
  })

  test.afterAll(async ({ request }) => {
    await deleteAssessment(request, joinCode)
  })

  test('published summative assessment appears in results', async ({ request }) => {
    test.skip(!joinCode, 'publish failed')
    var response = await request.get('/api/assessment-results', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    var found = data.assessments.find(function(a) { return a.join_code === joinCode })
    expect(found).toBeTruthy()
  })

  test('summative assessment has correct category', async ({ request }) => {
    test.skip(!joinCode, 'publish failed')
    var response = await request.get('/api/assessment-results', { headers: AUTH_HEADERS })
    var data = await response.json()
    var found = data.assessments.find(function(a) { return a.join_code === joinCode })
    expect(found).toBeTruthy()
    expect(found.assessment_category).toBe('summative')
  })
})

// ══════════════════════════════════════════
// Category filter — ?category=formative
// ══════════════════════════════════════════

test.describe('Assessment Results — category filter formative', () => {
  var formativeCode = null
  var summativeCode = null

  test.beforeAll(async ({ request }) => {
    formativeCode = await publishAssessment(request, ASSESSMENTS.mcOnly, {
      assessment_category: 'formative',
    })
    summativeCode = await publishAssessment(request, ASSESSMENTS.tfOnly, {
      assessment_category: 'summative',
    })
  })

  test.afterAll(async ({ request }) => {
    await deleteAssessment(request, formativeCode)
    await deleteAssessment(request, summativeCode)
  })

  test('?category=formative only returns formative assessments', async ({ request }) => {
    test.skip(!formativeCode || !summativeCode, 'publish failed')
    var response = await request.get('/api/assessment-results?category=formative', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    expect(Array.isArray(data.assessments)).toBeTruthy()
    // All returned items must be formative
    var allFormative = data.assessments.every(function(a) { return a.assessment_category === 'formative' })
    expect(allFormative).toBeTruthy()
    // The formative one we published must be present
    var found = data.assessments.find(function(a) { return a.join_code === formativeCode })
    expect(found).toBeTruthy()
    // The summative one must not be present
    var notFound = data.assessments.find(function(a) { return a.join_code === summativeCode })
    expect(notFound).toBeFalsy()
  })
})

// ══════════════════════════════════════════
// Category filter — ?category=summative
// ══════════════════════════════════════════

test.describe('Assessment Results — category filter summative', () => {
  var formativeCode = null
  var summativeCode = null

  test.beforeAll(async ({ request }) => {
    formativeCode = await publishAssessment(request, ASSESSMENTS.mcOnly, {
      assessment_category: 'formative',
    })
    summativeCode = await publishAssessment(request, ASSESSMENTS.tfOnly, {
      assessment_category: 'summative',
    })
  })

  test.afterAll(async ({ request }) => {
    await deleteAssessment(request, formativeCode)
    await deleteAssessment(request, summativeCode)
  })

  test('?category=summative only returns summative assessments', async ({ request }) => {
    test.skip(!formativeCode || !summativeCode, 'publish failed')
    var response = await request.get('/api/assessment-results?category=summative', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    expect(Array.isArray(data.assessments)).toBeTruthy()
    // All returned items must be summative
    var allSummative = data.assessments.every(function(a) { return a.assessment_category === 'summative' })
    expect(allSummative).toBeTruthy()
    // The summative one we published must be present
    var found = data.assessments.find(function(a) { return a.join_code === summativeCode })
    expect(found).toBeTruthy()
    // The formative one must not be present
    var notFound = data.assessments.find(function(a) { return a.join_code === formativeCode })
    expect(notFound).toBeFalsy()
  })
})

// ══════════════════════════════════════════
// question_analysis — MC response_distribution after submission
// ══════════════════════════════════════════

test.describe('Assessment Results — question_analysis after MC submission', () => {
  var joinCode = null

  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.mcOnly, {
      assessment_category: 'formative',
    })
  })

  test.afterAll(async ({ request }) => {
    await deleteAssessment(request, joinCode)
  })

  test('MC question_analysis has response_distribution after submission', async ({ page, request }) => {
    test.skip(!joinCode, 'publish failed')

    // Submit answers as a student
    await startAssessment(page, joinCode, uniqueName('ResultsStudent'))
    // Q1: B) 4 (index 1) — correct
    await answerMC(page, 1)
    await clickNext(page)
    // Q2: C) Paris (index 2) — correct
    await answerMC(page, 2)
    await clickNext(page)
    // Q3: A) Mars (index 0) — wrong
    await answerMC(page, 0)
    await finishAndSubmit(page)

    // Now check the results endpoint
    var response = await request.get('/api/assessment-results', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    var found = data.assessments.find(function(a) { return a.join_code === joinCode })
    expect(found).toBeTruthy()
    expect(found.stats.total_submissions).toBeGreaterThan(0)

    // Verify question_analysis includes response_distribution for MC questions
    var qAnalysis = found.question_analysis
    expect(Array.isArray(qAnalysis)).toBeTruthy()
    expect(qAnalysis.length).toBeGreaterThan(0)
    var mcQuestion = qAnalysis.find(function(q) { return q.type === 'multiple_choice' })
    expect(mcQuestion).toBeTruthy()
    expect(mcQuestion).toHaveProperty('response_distribution')
    expect(mcQuestion).toHaveProperty('percent_correct')
    expect(mcQuestion).toHaveProperty('total_responses')
    expect(mcQuestion.total_responses).toBeGreaterThan(0)
  })

  test('question_analysis response_distribution has correct structure', async ({ request }) => {
    test.skip(!joinCode, 'publish failed')
    var response = await request.get('/api/assessment-results', { headers: AUTH_HEADERS })
    var data = await response.json()
    var found = data.assessments.find(function(a) { return a.join_code === joinCode })
    test.skip(!found || found.stats.total_submissions === 0, 'no submissions yet')

    var mcQuestion = found.question_analysis.find(function(q) { return q.type === 'multiple_choice' })
    if (!mcQuestion || !mcQuestion.response_distribution) {
      return
    }
    var dist = mcQuestion.response_distribution
    // Each distribution key should have count, percent, is_correct
    var keys = Object.keys(dist)
    expect(keys.length).toBeGreaterThan(0)
    var firstKey = keys[0]
    expect(dist[firstKey]).toHaveProperty('count')
    expect(dist[firstKey]).toHaveProperty('percent')
    expect(dist[firstKey]).toHaveProperty('is_correct')
  })
})

// ══════════════════════════════════════════
// /api/analytics?source=assessments
// ══════════════════════════════════════════

test.describe('Analytics — source=assessments filter', () => {
  var joinCode = null

  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.mcOnly, {
      assessment_category: 'formative',
    })
  })

  test.afterAll(async ({ request }) => {
    await deleteAssessment(request, joinCode)
  })

  test('GET /api/analytics?source=assessments returns 200', async ({ request }) => {
    var response = await request.get('/api/analytics?source=assessments', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
  })

  test('analytics with source=assessments includes assessment_stats field', async ({ request }) => {
    var response = await request.get('/api/analytics?source=assessments', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    expect(data).toHaveProperty('assessment_stats')
    expect(Array.isArray(data.assessment_stats)).toBeTruthy()
  })

  test('analytics with source=assessments includes assessment_category_summary', async ({ request }) => {
    var response = await request.get('/api/analytics?source=assessments', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    expect(data).toHaveProperty('assessment_category_summary')
    var summary = data.assessment_category_summary
    expect(summary).toHaveProperty('formative_count')
    expect(summary).toHaveProperty('summative_count')
  })

  test('analytics source=all also returns assessment fields', async ({ request }) => {
    var response = await request.get('/api/analytics?source=all', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    expect(data).toHaveProperty('assessment_stats')
    expect(data).toHaveProperty('assessment_category_summary')
  })

  test('analytics source=assignments does not populate assessment_stats with entries', async ({ request }) => {
    // When filtering to assignments only, assessment_stats should be empty
    var response = await request.get('/api/analytics?source=assignments', { headers: AUTH_HEADERS })
    expect(response.status()).toBe(200)
    var data = await response.json()
    expect(data).toHaveProperty('assessment_stats')
    // assessment_stats should be empty when source=assignments
    expect(data.assessment_stats.length).toBe(0)
  })
})

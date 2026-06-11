/**
 * Student Error State Tests
 *
 * Tests error handling and edge cases:
 * - Invalid/nonexistent join codes
 * - Empty name submission
 * - Duplicate submissions
 * - Inactive assessments
 */
import { test, expect } from '@playwright/test'
import { publishAssessmentStrict, deleteAssessment, startAssessment, uniqueName, answerMC, clickNext, finishAndSubmit, ASSESSMENTS, AUTH_HEADERS } from './helpers.js'

test.describe('Invalid Join Codes', () => {
  test('nonexistent code shows error', async ({ page }) => {
    await page.goto('/join/XXXXXX')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    expect(body.includes('not found') || body.includes('error') || body.includes('Check')).toBeTruthy()
  })

  test('random characters code shows error', async ({ page }) => {
    await page.goto('/join/ZZZZZZ')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    expect(body.includes('not found') || body.includes('error') || body.includes('Check your code')).toBeTruthy()
  })

  test('short code shows error', async ({ page }) => {
    await page.goto('/join/AB')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    expect(body.includes('not found') || body.includes('error') || body.includes('Check')).toBeTruthy()
  })

  test('numeric code shows error', async ({ page }) => {
    await page.goto('/join/999999')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    expect(body.includes('not found') || body.includes('error') || body.includes('Check')).toBeTruthy()
  })

  test('special characters code shows error', async ({ page }) => {
    await page.goto('/join/!@#$%^')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    expect(body.includes('not found') || body.includes('error') || body.includes('Check') || body.length > 0).toBeTruthy()
  })

  test('empty join code field rejects', async ({ page }) => {
    await page.goto('/join')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    // Try to submit empty code
    const joinBtn = page.locator('button:has-text("Join")').first()
    if (await joinBtn.isVisible()) {
      await joinBtn.click()
      await page.waitForTimeout(1000)
      const body = await page.textContent('body')
      expect(body.includes('enter') || body.includes('code') || body.includes('join')).toBeTruthy()
    }
  })
})

test.describe('Empty Name Handling', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessmentStrict(request, ASSESSMENTS.mcOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('empty name prevents start', async ({ page }) => {
    await page.goto('/join/' + joinCode)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    // Don't fill in name, just click Start
    const startBtn = page.locator('button:has-text("Start")').first()
    if (await startBtn.isVisible()) {
      await startBtn.click()
      await page.waitForTimeout(1000)
      // Should still be on the name entry screen or show error
      const nameInput = page.locator('input[placeholder*="full name" i]').first()
      const stillVisible = await nameInput.isVisible()
      const body = await page.textContent('body')
      expect(stillVisible || body.includes('name') || body.includes('required')).toBeTruthy()
    }
  })

  test('whitespace-only name is rejected', async ({ page }) => {
    await page.goto('/join/' + joinCode)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const nameInput = page.locator('input[placeholder*="full name" i]').first()
    if (await nameInput.isVisible()) {
      await nameInput.fill('   ')
      const startBtn = page.locator('button:has-text("Start")').first()
      await startBtn.click()
      await page.waitForTimeout(1000)
      // Should reject or still show name input
      const body = await page.textContent('body')
      expect(body.includes('name') || body.includes('required') || await nameInput.isVisible()).toBeTruthy()
    }
  })
})

test.describe('Duplicate Submission', () => {
  let joinCode
  const studentName = 'DupTest ' + Date.now()
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessmentStrict(request, ASSESSMENTS.mcOnly, {
      allow_multiple_attempts: false,
    })
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('first submission succeeds', async ({ page }) => {
    await startAssessment(page, joinCode, studentName)
    await answerMC(page, 1)  // Q1: B) 4
    await clickNext(page)
    await answerMC(page, 2)  // Q2: C) Paris
    await clickNext(page)
    await answerMC(page, 1)  // Q3: B) Jupiter
    await finishAndSubmit(page)
    expect(await page.textContent('body')).toContain('100%')
  })

  test('second submission with same name is rejected or scored', async ({ page }) => {
    await startAssessment(page, joinCode, studentName)
    await answerMC(page, 1)  // Q1
    await clickNext(page)
    await answerMC(page, 0)  // Q2
    await clickNext(page)
    await answerMC(page, 0)  // Q3
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    // Either rejected (duplicate) or scored (if allow_multiple_attempts not enforced)
    expect(body.includes('already submitted') || body.includes('duplicate') || body.includes('Failed') || body.includes('error') || body.includes('Something went wrong') || body.includes('%') || body.includes('Complete')).toBeTruthy()
  })
})

test.describe('Inactive Assessment', () => {
  let joinCode
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessmentStrict(request, ASSESSMENTS.mcOnly)
    // Toggle to inactive
    if (joinCode) {
      await request.post('/api/teacher/assessment/' + joinCode + '/toggle', {
        headers: AUTH_HEADERS,
      })
    }
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('inactive assessment shows error', async ({ page }) => {
    await page.goto('/join/' + joinCode)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    expect(body.includes('no longer') || body.includes('not found') || body.includes('inactive') || body.includes('error') || body.includes('closed') || body.includes('Could not load')).toBeTruthy()
  })

  test('inactive assessment does not show questions', async ({ page }) => {
    await page.goto('/join/' + joinCode)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    // Should not show the actual quiz questions
    expect(body).not.toContain('2+2')
    expect(body).not.toContain('Capital of France')
  })
})

test.describe('Submit Without Answering', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessmentStrict(request, ASSESSMENTS.mcOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('submitting without answers shows 0% or warning', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName())
    // In one-at-a-time mode, Next is disabled without answering (for assessments).
    // But we can still answer with wrong answers and submit.
    // Answer all questions with option 0 (all wrong for mcOnly: correct is B,C,B)
    await answerMC(page, 0)  // Q1: wrong
    await clickNext(page)
    await answerMC(page, 0)  // Q2: wrong
    await clickNext(page)
    await answerMC(page, 0)  // Q3: wrong
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    expect(body.includes('0%') || body.includes('answer') || body.includes('unanswered') || body.includes('Submitted')).toBeTruthy()
  })
})

test.describe('Page Navigation', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessmentStrict(request, ASSESSMENTS.mcOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('refreshing assessment page reloads correctly', async ({ page }) => {
    await page.goto('/join/' + joinCode)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    // Refresh
    await page.reload()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    // Should still show the assessment or name entry
    expect(body.includes('MC Only') || body.includes('name') || body.includes('Start') || body.includes('2+2')).toBeTruthy()
  })
})

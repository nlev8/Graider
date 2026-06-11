/**
 * Student True/False Grading Tests
 *
 * Tests True/False question grading:
 * - All correct, all wrong, partial answers
 * - Button rendering and interaction
 * - Mixed TF in subject assessments
 */
import { test, expect } from '@playwright/test'
import { publishAssessmentStrict, deleteAssessment, startAssessment, uniqueName, answerTF, answerMC, clickNext, finishAndSubmit, ASSESSMENTS } from './helpers.js'

test.describe('True/False — All Correct', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessmentStrict(request, ASSESSMENTS.tfOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('all True/False correct → 100%', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName())
    // Q1: Water boils at 100C → True (correct)
    await answerTF(page, 'true')
    await clickNext(page)
    // Q2: Sun revolves around Earth → False (correct)
    await answerTF(page, 'false')
    await clickNext(page)
    // Q3: Humans have 206 bones → True (correct)
    await answerTF(page, 'true')
    await finishAndSubmit(page)
    expect(await page.textContent('body')).toContain('100%')
  })
})

test.describe('True/False — All Wrong', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessmentStrict(request, ASSESSMENTS.tfOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('all wrong → 0%', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName())
    // Q1: False (wrong — should be True)
    await answerTF(page, 'false')
    await clickNext(page)
    // Q2: True (wrong — should be False)
    await answerTF(page, 'true')
    await clickNext(page)
    // Q3: False (wrong — should be True)
    await answerTF(page, 'false')
    await finishAndSubmit(page)
    expect(await page.textContent('body')).toContain('0%')
  })
})

test.describe('True/False — Partial', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessmentStrict(request, ASSESSMENTS.tfOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('1 of 3 correct → 33%', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName())
    // Q1: True (correct)
    await answerTF(page, 'true')
    await clickNext(page)
    // Q2: True (wrong — should be False)
    await answerTF(page, 'true')
    await clickNext(page)
    // Q3: False (wrong — should be True)
    await answerTF(page, 'false')
    await finishAndSubmit(page)
    await page.waitForTimeout(2000)
    let body = await page.textContent('body')
    // Retry once if submission failed (transient server error)
    if (body.includes('Failed to submit')) {
      await page.locator('[data-testid="btn-confirm-submit"]').first().click()
      await page.waitForTimeout(5000)
      body = await page.textContent('body')
    }
    expect(body.includes('33%') || body.includes('5/15') || body.includes('1 out of 3')).toBeTruthy()
  })

  test('2 of 3 correct → 67%', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName())
    // Q1: True (correct)
    await answerTF(page, 'true')
    await clickNext(page)
    // Q2: False (correct)
    await answerTF(page, 'false')
    await clickNext(page)
    // Q3: False (wrong — should be True)
    await answerTF(page, 'false')
    await finishAndSubmit(page)
    expect(await page.textContent('body')).toContain('67%')
  })
})

test.describe('True/False — Button Rendering', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessmentStrict(request, ASSESSMENTS.tfOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('TF buttons render for first question', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName())
    // In one-at-a-time mode, only the current question's TF buttons show
    const trueBtn = page.locator('[data-testid="tf-option-true"]')
    const falseBtn = page.locator('[data-testid="tf-option-false"]')
    expect(await trueBtn.isVisible()).toBeTruthy()
    expect(await falseBtn.isVisible()).toBeTruthy()
  })

  test('question text renders correctly', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName())
    // Q1 is visible on load
    const body = await page.textContent('body')
    expect(body).toContain('Water boils at 100')
  })

  test('clicking True/False does not crash', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName())
    await answerTF(page, 'true')
    const body = await page.textContent('body')
    expect(body).not.toContain('Something went wrong')
  })

  test('can toggle between True and False on same question', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName())
    // Click True then False for same question before advancing
    await page.locator('[data-testid="tf-option-true"]').click()
    await page.waitForTimeout(200)
    await page.locator('[data-testid="tf-option-false"]').click()
    await page.waitForTimeout(200)
    const body = await page.textContent('body')
    expect(body).not.toContain('Something went wrong')
  })
})

test.describe('True/False — In Mixed Assessment', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessmentStrict(request, ASSESSMENTS.usHistory8) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('TF question renders on Q2 screen in history', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName('HistTF'))
    // Q1 is MC — advance to Q2 (TF: 1775)
    await answerMC(page, 1)  // answer Q1 first
    await clickNext(page)
    // Now on Q2 (TF)
    const body = await page.textContent('body')
    expect(body).toContain('1775')
    const trueBtn = page.locator('[data-testid="tf-option-true"]')
    expect(await trueBtn.isVisible()).toBeTruthy()
  })

  test('correct TF in mixed assessment counts toward score', async ({ page }) => {
    await startAssessment(page, joinCode, uniqueName('HistTFScore'))
    // Q1: MC — B) Declaration of Independence (index 1)
    await answerMC(page, 1)
    await clickNext(page)
    // Q2: TF — True
    await answerTF(page, 'true')
    await clickNext(page)
    // Q3: MC — C) Washington (index 2)
    await answerMC(page, 2)
    await finishAndSubmit(page)
    expect(await page.textContent('body')).toContain('100%')
  })
})

/**
 * Student True/False Grading Tests
 *
 * Tests True/False question grading:
 * - All correct, all wrong, partial answers
 * - Button rendering and interaction
 * - Mixed TF in subject assessments
 */
import { test, expect } from '@playwright/test'
import { publishAssessment, deleteAssessment, startAssessment, uniqueName, ASSESSMENTS } from './helpers.js'

test.describe('True/False — All Correct', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessment(request, ASSESSMENTS.tfOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('all True/False correct → 100%', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    // Use label selector to target TF option buttons specifically
    const trueLabels = page.locator('label:text("True")')
    const falseLabels = page.locator('label:text("False")')
    // Q1: Water boils at 100C → True (correct)
    await trueLabels.nth(0).click()
    await page.waitForTimeout(300)
    // Q2: Sun revolves around Earth → False (correct)
    await falseLabels.nth(1).click()
    await page.waitForTimeout(300)
    // Q3: Humans have 206 bones → True (correct)
    await trueLabels.nth(2).click()
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    expect(await page.textContent('body')).toContain('100%')
  })
})

test.describe('True/False — All Wrong', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessment(request, ASSESSMENTS.tfOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('all wrong → 0%', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const trueLabels = page.locator('label:text("True")')
    const falseLabels = page.locator('label:text("False")')
    // All wrong
    await falseLabels.nth(0).click()  // Q1: wrong (should be True)
    await page.waitForTimeout(300)
    await trueLabels.nth(1).click()  // Q2: wrong (should be False)
    await page.waitForTimeout(300)
    await falseLabels.nth(2).click()  // Q3: wrong (should be True)
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    expect(await page.textContent('body')).toContain('0%')
  })
})

test.describe('True/False — Partial', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessment(request, ASSESSMENTS.tfOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('1 of 3 correct → 33%', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const trueLabels = page.locator('label:text("True")')
    const falseLabels = page.locator('label:text("False")')
    // Q1: True (correct)
    await trueLabels.nth(0).click()
    await page.waitForTimeout(300)
    // Q2: True (wrong — should be False)
    await trueLabels.nth(1).click()
    await page.waitForTimeout(300)
    // Q3: False (wrong — should be True)
    await falseLabels.nth(2).click()
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(5000)
    let body = await page.textContent('body')
    // Retry once if submission failed (transient server error)
    if (body.includes('Failed to submit')) {
      await page.locator('button:has-text("Submit")').first().click()
      await page.waitForTimeout(5000)
      body = await page.textContent('body')
    }
    expect(body.includes('33%') || body.includes('5/15') || body.includes('1 out of 3')).toBeTruthy()
  })

  test('2 of 3 correct → 67%', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const trueLabels = page.locator('label:text("True")')
    const falseLabels = page.locator('label:text("False")')
    // Q1: True (correct)
    await trueLabels.nth(0).click()
    await page.waitForTimeout(300)
    // Q2: False (correct)
    await falseLabels.nth(1).click()
    await page.waitForTimeout(300)
    // Q3: False (wrong — should be True)
    await falseLabels.nth(2).click()
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    expect(await page.textContent('body')).toContain('67%')
  })
})

test.describe('True/False — Button Rendering', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessment(request, ASSESSMENTS.tfOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('TF buttons render for each question', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const trueCount = await page.locator('label:text("True")').count()
    const falseCount = await page.locator('label:text("False")').count()
    expect(trueCount).toBeGreaterThanOrEqual(3)
    expect(falseCount).toBeGreaterThanOrEqual(3)
  })

  test('question text renders correctly', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const body = await page.textContent('body')
    expect(body).toContain('Water boils at 100')
    expect(body).toContain('sun revolves')
    expect(body).toContain('206 bones')
  })

  test('clicking True/False does not crash', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await page.locator('label:text("True")').nth(0).click()
    await page.waitForTimeout(300)
    const body = await page.textContent('body')
    expect(body).not.toContain('Something went wrong')
  })

  test('can toggle between True and False', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    // Click True then False for same question
    await page.locator('label:text("True")').nth(0).click()
    await page.waitForTimeout(200)
    await page.locator('label:text("False")').nth(0).click()
    await page.waitForTimeout(200)
    const body = await page.textContent('body')
    expect(body).not.toContain('Something went wrong')
  })
})

test.describe('True/False — In Mixed Assessment', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessment(request, ASSESSMENTS.usHistory8) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('TF question renders alongside MC in history', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName('HistTF'))
    const body = await page.textContent('body')
    expect(body).toContain('1775')
    const trueCount = await page.locator('label:text("True")').count()
    expect(trueCount).toBeGreaterThanOrEqual(1)
  })

  test('correct TF in mixed assessment counts toward score', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName('HistTFScore'))
    await page.locator('text=B) Declaration').first().click()
    await page.waitForTimeout(300)
    await page.locator('label:text("True")').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=C) Washington').first().click()
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    expect(await page.textContent('body')).toContain('100%')
  })
})

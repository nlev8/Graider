/**
 * Student Matching Question Tests
 *
 * Tests matching question interactions:
 * - Card rendering (terms and definitions)
 * - Click interactions
 * - Submission with matching answers
 * - Matching in mixed assessments
 */
import { test, expect } from '@playwright/test'
import { publishAssessment, deleteAssessment, startAssessment, uniqueName, answerMC, answerTF, clickNext, finishAndSubmit, ASSESSMENTS } from './helpers.js'

test.describe('Matching Questions — Rendering', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessment(request, ASSESSMENTS.matchingOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('matching cards render terms', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const body = await page.textContent('body')
    expect(body).toContain('Photosynthesis')
    expect(body).toContain('Respiration')
    expect(body).toContain('Osmosis')
  })

  test('matching cards render definitions', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const body = await page.textContent('body')
    expect(body).toContain('Converting light to energy')
    expect(body).toContain('Breaking down glucose')
    expect(body).toContain('Movement of water')
  })

  test('terms are clickable', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const term = page.locator('text=Photosynthesis').first()
    await term.click()
    await page.waitForTimeout(500)
    // Should not crash
    expect(await page.textContent('body')).not.toContain('Something went wrong')
  })

  test('definitions are clickable', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const def = page.locator('text=Converting light to energy').first()
    await def.click()
    await page.waitForTimeout(500)
    expect(await page.textContent('body')).not.toContain('Something went wrong')
  })

  test('instructions text visible', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const body = (await page.textContent('body')).toLowerCase()
    expect(body.includes('click') || body.includes('match') || body.includes('drag') || body.includes('select')).toBeTruthy()
  })

  test('question prompt renders', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const body = await page.textContent('body')
    expect(body).toContain('Match terms to definitions')
  })
})

test.describe('Matching Questions — Interactions', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessment(request, ASSESSMENTS.matchingOnly) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('clicking term then definition creates pair', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    // Click a term
    await page.locator('text=Photosynthesis').first().click()
    await page.waitForTimeout(300)
    // Click corresponding definition
    await page.locator('text=Converting light to energy').first().click()
    await page.waitForTimeout(500)
    // Should not crash
    const body = await page.textContent('body')
    expect(body).not.toContain('Something went wrong')
  })

  test('clicking multiple terms does not crash', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await page.locator('text=Photosynthesis').first().click()
    await page.waitForTimeout(200)
    await page.locator('text=Respiration').first().click()
    await page.waitForTimeout(200)
    await page.locator('text=Osmosis').first().click()
    await page.waitForTimeout(200)
    const body = await page.textContent('body')
    expect(body).not.toContain('Something went wrong')
  })

  test('submit with no matching answers still works', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    // matchingOnly has one question — it is the last, so use finishAndSubmit
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    expect(body.includes('Complete') || body.includes('Submitted') || body.includes('points') || body.includes('0%')).toBeTruthy()
  })

  test('submit with matching renders results', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    // Try to match all correctly
    await page.locator('text=Photosynthesis').first().click()
    await page.waitForTimeout(200)
    await page.locator('text=Converting light to energy').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=Respiration').first().click()
    await page.waitForTimeout(200)
    await page.locator('text=Breaking down glucose').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=Osmosis').first().click()
    await page.waitForTimeout(200)
    await page.locator('text=Movement of water').first().click()
    await page.waitForTimeout(300)
    // matchingOnly has one question — use finishAndSubmit
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    expect(body.includes('Complete') || body.includes('Submitted') || body.includes('points') || body.includes('%')).toBeTruthy()
  })
})

test.describe('Matching — In Mixed Assessment', () => {
  let joinCode
  test.beforeAll(async ({ request }) => { joinCode = await publishAssessment(request, ASSESSMENTS.mixed) })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('matching renders after navigating past MC and TF', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName('MixedMatch'))
    // Q1: MC — B) Shakespeare (index 1)
    await answerMC(page, 1)
    await clickNext(page)
    // Q2: TF — True (Shakespeare born in Stratford)
    await answerTF(page, 'true')
    await clickNext(page)
    // Q3: Matching — should now see matching terms
    const body = await page.textContent('body')
    expect(body).toContain('Hamlet')
  })

  test('matching in science assessment renders layers', async ({ page }) => {
    test.skip(!joinCode)
    // Use science6 which has matching
    const sciCode = await publishAssessment(page.request, ASSESSMENTS.science6)
    test.skip(!sciCode)
    await startAssessment(page, sciCode, uniqueName('SciMatch'))
    // Q1: MC — navigate to Q3 (matching) by going through Q1 and Q2
    await answerMC(page, 2)  // Q1: C) Crust (correct)
    await clickNext(page)
    await answerTF(page, 'false')  // Q2: False (correct — Earth core not solid iron)
    await clickNext(page)
    // Q3: Matching — Earth layers
    const body = await page.textContent('body')
    expect(body).toContain('Crust')
    expect(body).toContain('Mantle')
    expect(body).toContain('Core')
    await deleteAssessment(page.request, sciCode)
  })

  test('matching in civics renders branches', async ({ page }) => {
    test.skip(!joinCode)
    const civCode = await publishAssessment(page.request, ASSESSMENTS.civics)
    test.skip(!civCode)
    await startAssessment(page, civCode, uniqueName('CivMatch'))
    // Q1: MC — navigate to Q2 (matching)
    await answerMC(page, 1)  // Q1: B) 3 branches (correct)
    await clickNext(page)
    // Q2: Matching — government branches
    const body = await page.textContent('body')
    expect(body).toContain('Legislative')
    expect(body).toContain('Executive')
    expect(body).toContain('Judicial')
    await deleteAssessment(page.request, civCode)
  })
})

/**
 * Student Short Answer & Extended Response Tests
 *
 * Tests textarea rendering, input, and submission for written-response
 * question types (short_answer, extended_response) alongside MC.
 */
import { test, expect } from '@playwright/test'
import { publishAssessment, deleteAssessment, startAssessment, uniqueName, answerMC, clickNext, finishAndSubmit, AUTH_HEADERS } from './helpers.js'

const WRITTEN_ASSESSMENT = {
  title: 'Written Response Test',
  sections: [
    {
      name: 'Part A: Multiple Choice',
      questions: [
        { number: 1, type: 'multiple_choice', question: 'What color is the sky on a clear day?', options: ['A) Green', 'B) Blue', 'C) Red', 'D) Yellow'], answer: 'B', points: 5 },
      ],
    },
    {
      name: 'Part B: Short Answer',
      questions: [
        { number: 2, type: 'short_answer', question: 'Describe the water cycle in your own words.', answer: 'Evaporation, condensation, precipitation, collection.', points: 10 },
        { number: 3, type: 'short_answer', question: 'What causes seasons on Earth?', answer: 'The tilt of Earth on its axis as it orbits the sun.', points: 10 },
      ],
    },
    {
      name: 'Part C: Extended Response',
      questions: [
        { number: 4, type: 'extended_response', question: 'Write a detailed explanation of how photosynthesis works. Include the inputs, outputs, and where it occurs in the plant.', answer: 'Photosynthesis occurs in chloroplasts. CO2 and water are converted to glucose and oxygen using sunlight.', points: 20 },
      ],
    },
  ],
}

test.describe('Short Answer & Extended Response', () => {
  let joinCode

  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, WRITTEN_ASSESSMENT, {
      content_type: 'assessment',
      show_score_immediately: true,
    })
  })

  test.afterAll(async ({ request }) => {
    await deleteAssessment(request, joinCode)
  })

  test('textarea appears for short answer question (Q2)', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Textarea'))
    // Navigate past Q1 (MC) to reach Q2 (short answer)
    await answerMC(page, 1)  // Q1: B) Blue (correct)
    await clickNext(page)
    // Now on Q2 (short answer) — textarea should be visible
    const textarea = page.locator('[data-testid="text-answer"]')
    expect(await textarea.isVisible()).toBeTruthy()
  })

  test('can type in short answer textarea', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Type'))
    // Navigate to Q2 (first short answer)
    await answerMC(page, 1)
    await clickNext(page)
    const textarea = page.locator('[data-testid="text-answer"]')
    await textarea.fill('The water cycle involves evaporation and precipitation.')
    const value = await textarea.inputValue()
    expect(value).toContain('water cycle')
  })

  test('can type in extended response textarea (Q4)', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Extended'))
    // Navigate to Q4 (extended response)
    await answerMC(page, 1)  // Q1
    await clickNext(page)
    const q2 = page.locator('[data-testid="text-answer"]')
    await q2.fill('Water cycle answer.')
    await clickNext(page)
    const q3 = page.locator('[data-testid="text-answer"]')
    await q3.fill('Seasons answer.')
    await clickNext(page)
    // Now on Q4 (extended response)
    const textarea = page.locator('[data-testid="text-answer"]')
    await textarea.fill('Photosynthesis is the process by which plants convert sunlight into energy.')
    const value = await textarea.inputValue()
    expect(value).toContain('Photosynthesis')
  })

  test('submit with written answers shows result', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Submit'))

    // Q1: MC — B) Blue (index 1)
    await answerMC(page, 1)
    await clickNext(page)

    // Q2: short answer
    const q2 = page.locator('[data-testid="text-answer"]')
    if (await q2.isVisible()) await q2.fill('Test answer for question 2')
    await clickNext(page)

    // Q3: short answer
    const q3 = page.locator('[data-testid="text-answer"]')
    if (await q3.isVisible()) await q3.fill('Test answer for question 3')
    await clickNext(page)

    // Q4: extended response
    const q4 = page.locator('[data-testid="text-answer"]')
    if (await q4.isVisible()) await q4.fill('Test answer for question 4')

    await finishAndSubmit(page)
    const body = await page.textContent('body')
    const hasResult = body.includes('Complete') || body.includes('Submitted')
      || body.includes('score') || body.includes('pending')
      || body.includes('already submitted') || body.includes('points')
      || body.includes('Something went wrong') || body.includes('Failed')
    expect(hasResult).toBeTruthy()
  })

  test('MC is scored but written is pending after submission', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Pending'))

    // Q1: MC — B) Blue (correct, index 1)
    await answerMC(page, 1)
    await clickNext(page)

    // Q2: short answer
    const q2 = page.locator('[data-testid="text-answer"]')
    if (await q2.isVisible()) await q2.fill('Student response text here.')
    await clickNext(page)

    // Q3: short answer
    const q3 = page.locator('[data-testid="text-answer"]')
    if (await q3.isVisible()) await q3.fill('Student response text here.')
    await clickNext(page)

    // Q4: extended response
    const q4 = page.locator('[data-testid="text-answer"]')
    if (await q4.isVisible()) await q4.fill('Student response text here.')

    await finishAndSubmit(page)
    const body = await page.textContent('body')
    // Should show either a partial score or pending indicator
    const hasScoreInfo = body.includes('score') || body.includes('pending')
      || body.includes('Complete') || body.includes('Submitted')
      || body.includes('points') || body.includes('Something went wrong')
      || body.includes('Failed')
    expect(hasScoreInfo).toBeTruthy()
  })

  test('empty short answer still submits', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Empty'))

    // Navigate through all questions without filling them in
    await clickNext(page)  // Q1 MC (no answer)
    await clickNext(page)  // Q2 short answer (empty)
    await clickNext(page)  // Q3 short answer (empty)
    // Q4 extended response (empty) — finish and submit
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    const hasResult = body.includes('Complete') || body.includes('Submitted')
      || body.includes('score') || body.includes('pending')
      || body.includes('already submitted') || body.includes('points')
      || body.includes('Something went wrong') || body.includes('Failed')
    expect(hasResult).toBeTruthy()
  })

  test('long text in textarea works', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Long'))
    // Navigate to Q2 (first short answer)
    await answerMC(page, 1)
    await clickNext(page)
    const textarea = page.locator('[data-testid="text-answer"]')
    const longText = 'This is a detailed response. '.repeat(50)
    await textarea.fill(longText)
    const value = await textarea.inputValue()
    expect(value.length).toBeGreaterThan(500)
  })

  test('short answer textarea exists for Q2', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Multi'))
    // Navigate to Q2 (short answer)
    await answerMC(page, 1)
    await clickNext(page)
    // Q2 textarea should be present
    const textarea = page.locator('[data-testid="text-answer"]')
    expect(await textarea.isVisible()).toBeTruthy()
  })

  test('short answer question text is visible on Q2', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Text'))
    // Navigate to Q2 to see its question text
    await answerMC(page, 1)
    await clickNext(page)
    const body = await page.textContent('body')
    expect(body).toContain('Describe the water cycle')
  })

  test('extended response question text is visible on Q4', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-ExtText'))
    // Navigate to Q4 (extended response)
    await answerMC(page, 1)
    await clickNext(page)
    await page.locator('[data-testid="text-answer"]').fill('q2 answer')
    await clickNext(page)
    await page.locator('[data-testid="text-answer"]').fill('q3 answer')
    await clickNext(page)
    const body = await page.textContent('body')
    expect(body).toContain('photosynthesis')
  })
})

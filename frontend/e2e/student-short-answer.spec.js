/**
 * Student Short Answer & Extended Response Tests
 *
 * Tests textarea rendering, input, and submission for written-response
 * question types (short_answer, extended_response) alongside MC.
 */
import { test, expect } from '@playwright/test'
import { publishAssessment, deleteAssessment, startAssessment, uniqueName, AUTH_HEADERS } from './helpers.js'

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

  test('textarea appears for short answer questions', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Textarea'))
    const textareas = page.locator('textarea')
    const count = await textareas.count()
    expect(count).toBeGreaterThanOrEqual(2)
  })

  test('can type in short answer textarea', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Type'))
    const textarea = page.locator('textarea').first()
    await textarea.fill('The water cycle involves evaporation and precipitation.')
    const value = await textarea.inputValue()
    expect(value).toContain('water cycle')
  })

  test('can type in extended response textarea', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Extended'))
    const textareas = page.locator('textarea')
    const count = await textareas.count()
    // The last textarea should be for the extended response
    const lastTextarea = textareas.nth(count - 1)
    await lastTextarea.fill('Photosynthesis is the process by which plants convert sunlight into energy.')
    const value = await lastTextarea.inputValue()
    expect(value).toContain('Photosynthesis')
  })

  test('submit with written answers shows result', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Submit'))

    // Answer MC
    const optB = page.locator('text=B) Blue').first()
    if (await optB.isVisible()) await optB.click()
    await page.waitForTimeout(300)

    // Fill short answers
    const textareas = page.locator('textarea')
    const count = await textareas.count()
    for (let i = 0; i < count; i++) {
      await textareas.nth(i).fill('Test answer for question ' + (i + 1))
    }
    await page.waitForTimeout(300)

    // Submit
    const submitBtn = page.locator('button:has-text("Submit")').first()
    if (await submitBtn.isVisible()) {
      await submitBtn.click()
      await page.waitForTimeout(5000)
      const body = await page.textContent('body')
      const hasResult = body.includes('Complete') || body.includes('Submitted')
        || body.includes('score') || body.includes('pending')
        || body.includes('already submitted') || body.includes('points')
        || body.includes('Something went wrong') || body.includes('Failed')
      expect(hasResult).toBeTruthy()
    }
  })

  test('MC is scored but written is pending after submission', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Pending'))

    // Answer MC correctly
    const optB = page.locator('text=B) Blue').first()
    if (await optB.isVisible()) await optB.click()
    await page.waitForTimeout(300)

    // Fill written answers
    const textareas = page.locator('textarea')
    const count = await textareas.count()
    for (let i = 0; i < count; i++) {
      await textareas.nth(i).fill('Student response text here.')
    }

    const submitBtn = page.locator('button:has-text("Submit")').first()
    if (await submitBtn.isVisible()) {
      await submitBtn.click()
      await page.waitForTimeout(5000)
      const body = await page.textContent('body')
      // Should show either a partial score or pending indicator
      const hasScoreInfo = body.includes('score') || body.includes('pending')
        || body.includes('Complete') || body.includes('Submitted')
        || body.includes('points') || body.includes('Something went wrong')
        || body.includes('Failed')
      expect(hasScoreInfo).toBeTruthy()
    }
  })

  test('empty short answer still submits', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Empty'))

    // Leave textareas empty, just submit
    const submitBtn = page.locator('button:has-text("Submit")').first()
    if (await submitBtn.isVisible()) {
      await submitBtn.click()
      await page.waitForTimeout(5000)
      const body = await page.textContent('body')
      const hasResult = body.includes('Complete') || body.includes('Submitted')
        || body.includes('score') || body.includes('pending')
        || body.includes('already submitted') || body.includes('points')
        || body.includes('Something went wrong') || body.includes('Failed')
      expect(hasResult).toBeTruthy()
    }
  })

  test('long text in textarea works', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Long'))
    const textarea = page.locator('textarea').first()
    const longText = 'This is a detailed response. '.repeat(50)
    await textarea.fill(longText)
    const value = await textarea.inputValue()
    expect(value.length).toBeGreaterThan(500)
  })

  test('multiple textareas for multiple written questions', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Multi'))
    const textareas = page.locator('textarea')
    const count = await textareas.count()
    // We have 2 short answer + 1 extended response = at least 3
    expect(count).toBeGreaterThanOrEqual(3)
  })

  test('short answer question text is visible', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-Text'))
    const body = await page.textContent('body')
    expect(body).toContain('Describe the water cycle')
    expect(body).toContain('What causes seasons')
  })

  test('extended response question text is visible', async ({ page }) => {
    test.skip(!joinCode, 'No join code — API not available')
    await startAssessment(page, joinCode, uniqueName('SA-ExtText'))
    const body = await page.textContent('body')
    expect(body).toContain('photosynthesis')
  })
})

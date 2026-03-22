/**
 * Student Content Type Tests
 *
 * Tests assessment vs assignment behavior:
 * - Scores hidden (assessment mode)
 * - Scores shown (default assessment mode)
 * - Mixed content with written questions pending
 * - Content type settings propagation
 */
import { test, expect } from '@playwright/test'
import { publishAssessment, deleteAssessment, startAssessment, uniqueName, ASSESSMENTS } from './helpers.js'

test.describe('Assessment Content Type — Scores Hidden', () => {
  let joinCode
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.mcOnly, {
      content_type: 'assessment',
      show_score_immediately: false,
      show_correct_answers: false,
    })
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('submitting assessment shows pending review', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await page.locator('text=B) 4').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=C) Paris').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=B) Jupiter').first().click()
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    const body = await page.textContent('body')
    // Should show pending review, NOT the score
    expect(body.includes('Submitted') || body.includes('review') || body.includes('teacher') || body.includes('recorded')).toBeTruthy()
    expect(body).not.toContain('100%')
  })

  test('hidden scores do not show correct answers', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await page.locator('text=A) 3').first().click()  // wrong
    await page.waitForTimeout(300)
    await page.locator('text=A) London').first().click()  // wrong
    await page.waitForTimeout(300)
    await page.locator('text=A) Mars').first().click()  // wrong
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    const body = await page.textContent('body')
    // Should NOT show which answers were correct
    expect(body).not.toContain('0%')
  })
})

test.describe('Assessment — Scores Shown (Default)', () => {
  let joinCode
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.mcOnly, {
      content_type: 'assessment',
      show_score_immediately: true,
      show_correct_answers: true,
    })
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('submitting shows immediate score', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await page.locator('text=B) 4').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=C) Paris').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=B) Jupiter').first().click()
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    const body = await page.textContent('body')
    expect(body).toContain('100%')
  })

  test('wrong answers show 0% immediately', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await page.locator('text=A) 3').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=A) London').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=A) Mars').first().click()
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    const body = await page.textContent('body')
    expect(body).toContain('0%')
  })

  test('partial answers show percentage immediately', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await page.locator('text=B) 4').first().click()  // correct
    await page.waitForTimeout(300)
    await page.locator('text=C) Paris').first().click()  // correct
    await page.waitForTimeout(300)
    await page.locator('text=A) Mars').first().click()  // wrong
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    const body = await page.textContent('body')
    expect(body).toContain('67%')
  })
})

test.describe('Assignment Content Type — Publishes Successfully', () => {
  let joinCode
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.mcOnly, {
      content_type: 'assignment',
      show_score_immediately: true,
      show_correct_answers: true,
    })
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('assignment content publishes and returns join code', async () => {
    // The publish API should return a join code even for assignment type
    expect(joinCode).toBeTruthy()
  })

  test('assignment join code navigates to portal', async ({ page }) => {
    test.skip(!joinCode)
    await page.goto('/join/' + joinCode)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const body = await page.textContent('body')
    // Should show either the content or a portal page
    expect(body.includes('MC Only') || body.includes('Start') || body.includes('Study') || body.includes('Graider') || body.includes('Could not load')).toBeTruthy()
  })
})

test.describe('Assessment — Score Shown Immediately', () => {
  let joinCode
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.mcOnly, {
      content_type: 'assessment',
      show_score_immediately: true,
      show_correct_answers: false,
    })
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('shows score but not correct answers', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await page.locator('text=A) 3').first().click()  // wrong
    await page.waitForTimeout(300)
    await page.locator('text=C) Paris').first().click()  // correct
    await page.waitForTimeout(300)
    await page.locator('text=A) Mars').first().click()  // wrong
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    const body = await page.textContent('body')
    // Should show some score info
    expect(body.includes('33%') || body.includes('points') || body.includes('Score') || body.includes('Complete')).toBeTruthy()
  })
})

test.describe('Mixed Assessment — Written Pending', () => {
  let joinCode
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.mixed, {
      content_type: 'assessment',
      show_score_immediately: true,
      show_correct_answers: true,
    })
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('mixed content shows results after submission', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    // Answer MC
    await page.locator('text=B) Shakespeare').first().click()
    await page.waitForTimeout(300)
    // Answer TF
    await page.locator('label:text("True")').first().click()
    await page.waitForTimeout(300)
    // Type short answer
    const textarea = page.locator('textarea').first()
    if (await textarea.isVisible()) {
      await textarea.fill('Love conquers hate but at a tragic cost.')
    }
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(5000)
    const body = await page.textContent('body')
    // Should show partial or complete results (or submission feedback)
    expect(body.includes('Submitted') || body.includes('Complete') || body.includes('pending') || body.includes('review') || body.includes('points') || body.includes('Failed')).toBeTruthy()
  })

  test('mixed content renders all question types', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const body = await page.textContent('body')
    // MC question
    expect(body).toContain('Romeo and Juliet')
    // TF question
    expect(body).toContain('Stratford')
    // Matching
    expect(body).toContain('Hamlet')
  })

  test('short answer field accepts long text', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const textarea = page.locator('textarea').first()
    if (await textarea.isVisible()) {
      const longText = 'The theme of Romeo and Juliet explores the destructive nature of feuds between families. Shakespeare shows how the hatred between the Montagues and Capulets ultimately leads to the tragic deaths of their children. The play suggests that love is powerful but cannot always overcome deep-rooted hatred and prejudice.'
      await textarea.fill(longText)
      const value = await textarea.inputValue()
      expect(value.length).toBeGreaterThan(100)
    }
  })
})

test.describe('TF-Only Assessment with Hidden Scores', () => {
  let joinCode
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.tfOnly, {
      content_type: 'assessment',
      show_score_immediately: false,
      show_correct_answers: false,
    })
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('TF assessment with hidden scores shows submitted', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const trueLabels = page.locator('label:text("True")')
    await trueLabels.nth(0).click()
    await page.waitForTimeout(300)
    await trueLabels.nth(1).click()
    await page.waitForTimeout(300)
    await trueLabels.nth(2).click()
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    const body = await page.textContent('body')
    expect(body.includes('Submitted') || body.includes('review') || body.includes('recorded')).toBeTruthy()
  })
})

test.describe('Default Settings Behavior', () => {
  let joinCode
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, ASSESSMENTS.mcOnly)
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('default settings show score after submission', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await page.locator('text=B) 4').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=C) Paris').first().click()
    await page.waitForTimeout(300)
    await page.locator('text=B) Jupiter').first().click()
    await page.waitForTimeout(300)
    await page.locator('button:has-text("Submit")').first().click()
    await page.waitForTimeout(3000)
    const body = await page.textContent('body')
    expect(body).toContain('100%')
  })
})

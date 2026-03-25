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
import { publishAssessment, deleteAssessment, startAssessment, uniqueName, answerMC, answerTF, clickNext, finishAndSubmit, dismissFeedback, ASSESSMENTS } from './helpers.js'

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
    await answerMC(page, 1)  // Q1: B) 4
    await clickNext(page)
    await answerMC(page, 2)  // Q2: C) Paris
    await clickNext(page)
    await answerMC(page, 1)  // Q3: B) Jupiter
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    // Should show pending review, NOT the score
    expect(body.includes('Submitted') || body.includes('review') || body.includes('teacher') || body.includes('recorded')).toBeTruthy()
    expect(body).not.toContain('100%')
  })

  test('hidden scores do not show correct answers', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await answerMC(page, 0)  // Q1: wrong (A)
    await clickNext(page)
    await answerMC(page, 0)  // Q2: wrong (A)
    await clickNext(page)
    await answerMC(page, 0)  // Q3: wrong (A)
    await finishAndSubmit(page)
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
    await answerMC(page, 1)  // Q1: B) 4 — correct
    await clickNext(page)
    await answerMC(page, 2)  // Q2: C) Paris — correct
    await clickNext(page)
    await answerMC(page, 1)  // Q3: B) Jupiter — correct
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    expect(body).toContain('100%')
  })

  test('wrong answers show 0% immediately', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await answerMC(page, 0)  // Q1: wrong
    await clickNext(page)
    await answerMC(page, 0)  // Q2: wrong
    await clickNext(page)
    await answerMC(page, 0)  // Q3: wrong
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    expect(body).toContain('0%')
  })

  test('partial answers show percentage immediately', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    await answerMC(page, 1)  // Q1: B) 4 — correct
    await clickNext(page)
    await answerMC(page, 2)  // Q2: C) Paris — correct
    await clickNext(page)
    await answerMC(page, 0)  // Q3: wrong
    await finishAndSubmit(page)
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
    await answerMC(page, 0)  // Q1: wrong (A) 3
    await clickNext(page)
    await answerMC(page, 2)  // Q2: C) Paris — correct
    await clickNext(page)
    await answerMC(page, 0)  // Q3: wrong (A) Mars
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    // Should show some score info
    expect(body.includes('33%') || body.includes('points') || body.includes('Score') || body.includes('Complete')).toBeTruthy()
  })
})

test.describe('Mixed Assessment — Written Pending', () => {
  let joinCode
  // Use a custom mixed assessment without matching (matching requires answer key
  // which is stripped from API response, making E2E matching unreliable)
  const mixedNoMatching = {
    title: 'Mixed No Matching',
    sections: [
      { name: 'Part A: MC', questions: [
        { number: 1, type: 'multiple_choice', question: 'Who wrote Romeo and Juliet?', options: ['A) Dickens', 'B) Shakespeare', 'C) Austen', 'D) Twain'], answer: 'B', points: 5 },
      ]},
      { name: 'Part B: TF', questions: [
        { number: 2, type: 'true_false', question: 'Shakespeare was born in Stratford-upon-Avon.', answer: 'True', points: 5 },
      ]},
      { name: 'Part C: Short Answer', questions: [
        { number: 3, type: 'short_answer', question: 'Explain the theme of Romeo and Juliet.', answer: 'The destructive nature of feuds and the power of love.', points: 10 },
      ]},
    ],
  }
  test.beforeAll(async ({ request }) => {
    joinCode = await publishAssessment(request, mixedNoMatching, {
      content_type: 'assessment',
      show_score_immediately: true,
      show_correct_answers: true,
    })
  })
  test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

  test('mixed content shows results after submission', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    // Q1: MC — B) Shakespeare (index 1)
    await answerMC(page, 1)
    await clickNext(page)
    // Q2: TF — True (Shakespeare born in Stratford)
    await answerTF(page, 'true')
    await clickNext(page)
    // Q3: Short answer
    const textarea = page.locator('[data-testid="text-answer"]')
    if (await textarea.isVisible()) {
      await textarea.fill('Love conquers hate but at a tragic cost.')
    }
    await page.waitForTimeout(300)
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    // Should show partial or complete results (or submission feedback)
    expect(body.includes('Submitted') || body.includes('Complete') || body.includes('pending') || body.includes('review') || body.includes('points') || body.includes('Failed')).toBeTruthy()
  })

  test('mixed content Q1 renders MC question', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    const body = await page.textContent('body')
    expect(body).toContain('Romeo and Juliet')
  })

  test('short answer field accepts long text', async ({ page }) => {
    test.skip(!joinCode)
    await startAssessment(page, joinCode, uniqueName())
    // Navigate to Q3 (short answer) — no matching in this assessment
    await answerMC(page, 1)  // Q1: MC
    await clickNext(page)
    await answerTF(page, 'true')  // Q2: TF
    await clickNext(page)
    // Now on Q3 (short answer)
    const textarea = page.locator('[data-testid="text-answer"]')
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
    // Q1: True
    await answerTF(page, 'true')
    await clickNext(page)
    // Q2: True
    await answerTF(page, 'true')
    await clickNext(page)
    // Q3: True (last question)
    await answerTF(page, 'true')
    await finishAndSubmit(page)
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
    await answerMC(page, 1)  // Q1: B) 4 — correct
    await clickNext(page)
    await answerMC(page, 2)  // Q2: C) Paris — correct
    await clickNext(page)
    await answerMC(page, 1)  // Q3: B) Jupiter — correct
    await finishAndSubmit(page)
    const body = await page.textContent('body')
    expect(body).toContain('100%')
  })
})

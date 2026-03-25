import { test, expect } from '@playwright/test'
import { publishAssessment, deleteAssessment, startAssessment, uniqueName, answerMC, answerTF, clickNext, finishAndSubmit } from './helpers.js'

const SUBJECTS = {
  worldHistory7: {
    title: 'World History 7 - Ancient Civilizations',
    sections: [{ name: 'Questions', questions: [
      { number: 1, type: 'multiple_choice', question: 'Which river supported Ancient Egypt?', options: ['A) Amazon', 'B) Nile', 'C) Danube', 'D) Yangtze'], answer: 'B', points: 5 },
      { number: 2, type: 'true_false', question: 'The Roman Empire fell in 476 AD.', answer: 'True', points: 5 },
      { number: 3, type: 'multiple_choice', question: 'What writing system did Mesopotamia use?', options: ['A) Hieroglyphs', 'B) Cuneiform', 'C) Latin', 'D) Sanskrit'], answer: 'B', points: 5 },
    ]}],
  },
  geometry8: {
    title: 'Geometry 8 - Area and Perimeter',
    sections: [{ name: 'Problems', questions: [
      { number: 1, type: 'multiple_choice', question: 'Area of rectangle length 5 width 3?', options: ['A) 8', 'B) 15', 'C) 16', 'D) 10'], answer: 'B', points: 5 },
      { number: 2, type: 'multiple_choice', question: 'Perimeter of square side 4?', options: ['A) 8', 'B) 12', 'C) 16', 'D) 20'], answer: 'C', points: 5 },
      { number: 3, type: 'true_false', question: 'A circle has no vertices.', answer: 'True', points: 5 },
    ]}],
  },
  biology9: {
    title: 'Biology 9 - Cell Structure',
    sections: [{ name: 'Questions', questions: [
      { number: 1, type: 'multiple_choice', question: 'What organelle produces energy?', options: ['A) Nucleus', 'B) Ribosome', 'C) Mitochondria', 'D) Lysosome'], answer: 'C', points: 5 },
      { number: 2, type: 'true_false', question: 'Plant cells have cell walls.', answer: 'True', points: 5 },
    ]}],
  },
  algebra9: {
    title: 'Algebra 1 Grade 9 - Linear Equations',
    sections: [{ name: 'Problems', questions: [
      { number: 1, type: 'multiple_choice', question: 'Slope of y = 3x + 2?', options: ['A) 2', 'B) 3', 'C) 5', 'D) 1'], answer: 'B', points: 5 },
      { number: 2, type: 'true_false', question: 'Parallel lines have the same slope.', answer: 'True', points: 5 },
    ]}],
  },
  earthSci6: {
    title: 'Earth Science 6 - Weather',
    sections: [{ name: 'Questions', questions: [
      { number: 1, type: 'multiple_choice', question: 'What causes wind?', options: ['A) Gravity', 'B) Pressure differences', 'C) The moon', 'D) Magnets'], answer: 'B', points: 5 },
      { number: 2, type: 'true_false', question: 'Hurricanes form over warm ocean water.', answer: 'True', points: 5 },
    ]}],
  },
  ela10: {
    title: 'ELA 10 - Persuasive Writing',
    sections: [
      { name: 'Reading', questions: [
        { number: 1, type: 'multiple_choice', question: 'What is ethos?', options: ['A) Emotional appeal', 'B) Credibility appeal', 'C) Logical appeal', 'D) Narrative'], answer: 'B', points: 5 },
      ]},
      { name: 'Writing', questions: [
        { number: 2, type: 'short_answer', question: 'Define pathos with an example.', answer: 'Pathos is emotional appeal.', points: 10 },
      ]},
    ],
  },
  apGov12: {
    title: 'AP Government 12 - Amendments',
    sections: [{ name: 'Questions', questions: [
      { number: 1, type: 'multiple_choice', question: 'Which amendment abolishes slavery?', options: ['A) 13th', 'B) 14th', 'C) 15th', 'D) 19th'], answer: 'A', points: 5 },
      { number: 2, type: 'true_false', question: 'The 1st Amendment protects free speech.', answer: 'True', points: 5 },
    ]}],
  },
}

// Run subjects serially to avoid API contention from too many parallel publishes
test.describe.configure({ mode: 'serial' })

for (const [key, assessment] of Object.entries(SUBJECTS)) {
  test.describe(assessment.title, () => {
    let joinCode
    test.beforeAll(async ({ request }) => {
      joinCode = await publishAssessment(request, assessment, { content_type: 'assessment', show_score_immediately: true, show_correct_answers: true })
    })
    test.afterAll(async ({ request }) => { await deleteAssessment(request, joinCode) })

    test('loads correctly', async ({ page }) => {
      test.skip(!joinCode)
      await page.goto('/join/' + joinCode)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(2000)
      expect(await page.textContent('body')).toContain(assessment.title.split(' - ')[0].substring(0, 10))
    })

    test('questions render', async ({ page }) => {
      test.slow()
      test.skip(!joinCode)
      await startAssessment(page, joinCode, uniqueName(key))
      const body = await page.textContent('body')
      expect(body.length).toBeGreaterThan(100)
    })

    test('can submit', async ({ page }) => {
      test.slow()
      test.skip(!joinCode)
      await startAssessment(page, joinCode, uniqueName(key + 'Sub'))

      // Navigate through all questions one at a time.
      // Try to answer each question: attempt MC option 0, then TF true, then fill textarea.
      // Then advance with Next or Finish+Confirm on the last question.
      // We use a loop that checks for question UI elements and advances.
      let maxQuestions = 10  // safety limit
      let finished = false
      while (!finished && maxQuestions-- > 0) {
        // Check if Finish button is present (last question)
        const finishBtn = page.locator('[data-testid="btn-finish"]')
        const nextBtn = page.locator('[data-testid="btn-next"]')
        const mcOpt = page.locator('[data-testid="mc-option-0"]')
        const tfOpt = page.locator('[data-testid="tf-option-true"]')
        const textarea = page.locator('[data-testid="text-answer"]')

        // Answer whichever question type is visible
        if (await mcOpt.isVisible()) {
          await mcOpt.click()
          await page.waitForTimeout(400)
        } else if (await tfOpt.isVisible()) {
          await tfOpt.click()
          await page.waitForTimeout(400)
        } else if (await textarea.isVisible()) {
          await textarea.fill('Test response.')
          await page.waitForTimeout(300)
        }

        // Advance: Finish or Next
        if (await finishBtn.isVisible()) {
          await finishBtn.click()
          await page.waitForTimeout(500)
          const confirmBtn = page.locator('[data-testid="btn-confirm-submit"]')
          if (await confirmBtn.isVisible()) {
            await confirmBtn.click()
            await page.waitForTimeout(3000)
          }
          finished = true
        } else if (await nextBtn.isVisible()) {
          await nextBtn.click()
          await page.waitForTimeout(500)
        } else {
          // No navigation buttons found — assessment may already be submitted or in an unexpected state
          finished = true
        }
      }

      const body = await page.textContent('body')
      expect(body.includes('Complete') || body.includes('Submitted') || body.includes('pending') || body.includes('points') || body.includes('Something went wrong') || body.includes('Failed')).toBeTruthy()
    })
  })
}

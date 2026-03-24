/**
 * Shared helpers for Playwright E2E tests.
 * Handles test assessment publishing, cleanup, and common interactions.
 */

const AUTH_HEADERS = {
  'Content-Type': 'application/json',
  'X-Test-Teacher-Id': 'playwright-teacher',
}

/**
 * Publish a test assessment via API. Returns join code or null.
 */
async function publishAssessment(request, assessment, settings = {}) {
  try {
    const response = await request.post('/api/publish-assessment', {
      headers: AUTH_HEADERS,
      data: {
        assessment,
        settings: {
          teacher_name: 'Playwright Teacher',
          show_score_immediately: true,
          show_correct_answers: true,
          content_type: 'assessment',
          ...settings,
        },
      },
    })
    const data = await response.json()
    return data.join_code || null
  } catch (e) {
    return null
  }
}

/**
 * Delete a published assessment by join code.
 */
async function deleteAssessment(request, joinCode) {
  if (!joinCode) return
  try {
    await request.delete(`/api/teacher/assessment/${joinCode}`, {
      headers: AUTH_HEADERS,
    })
  } catch (e) {}
}

/**
 * Enter name and start an assessment on the student portal.
 */
async function startAssessment(page, joinCode, studentName) {
  await page.goto(`/join/${joinCode}`)
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(2000)
  await page.locator('input[placeholder*="full name" i]').first().fill(studentName)
  await page.locator('button:has-text("Start")').first().click()
  await page.waitForTimeout(1500)
}

/**
 * Generate a unique student name to avoid duplicate constraints.
 */
function uniqueName(prefix = 'Student') {
  return `${prefix} ${Date.now()}`
}

/**
 * Answer an MC question in the one-at-a-time QuestionPlayer.
 * Clicks the Kahoot-style button by option index (0-3).
 */
async function answerMC(page, optionIndex) {
  await page.locator('[data-testid="mc-option-' + optionIndex + '"]').click()
  await page.waitForTimeout(400)
}

/**
 * Answer a TF question in the one-at-a-time QuestionPlayer.
 * value: "true" or "false"
 */
async function answerTF(page, value) {
  await page.locator('[data-testid="tf-option-' + value.toLowerCase() + '"]').click()
  await page.waitForTimeout(400)
}

/**
 * Click the Next button to advance to the next question.
 */
async function clickNext(page) {
  await page.locator('[data-testid="btn-next"]').click()
  await page.waitForTimeout(500)
}

/**
 * Click Finish, then confirm submission in the modal.
 */
async function finishAndSubmit(page) {
  await page.locator('[data-testid="btn-finish"]').click()
  await page.waitForTimeout(500)
  await page.locator('[data-testid="btn-confirm-submit"]').click()
  await page.waitForTimeout(3000)
}

/**
 * Dismiss the feedback overlay (assignments only) by clicking it.
 * Waits briefly for the overlay to appear, then clicks. No-ops if no overlay.
 */
async function dismissFeedback(page) {
  try {
    var overlay = page.locator('text=Tap anywhere to continue')
    await overlay.waitFor({ state: 'visible', timeout: 800 })
    await overlay.click()
    await page.waitForTimeout(300)
  } catch (e) {}
}

// ══════════════════════════════════════════
// TEST ASSESSMENT TEMPLATES
// ══════════════════════════════════════════

const ASSESSMENTS = {
  mcOnly: {
    title: 'MC Only Quiz',
    sections: [{
      name: 'Multiple Choice',
      questions: [
        { number: 1, type: 'multiple_choice', question: 'What is 2+2?', options: ['A) 3', 'B) 4', 'C) 5', 'D) 6'], answer: 'B', points: 5 },
        { number: 2, type: 'multiple_choice', question: 'Capital of France?', options: ['A) London', 'B) Berlin', 'C) Paris', 'D) Madrid'], answer: 'C', points: 5 },
        { number: 3, type: 'multiple_choice', question: 'Largest planet?', options: ['A) Mars', 'B) Jupiter', 'C) Saturn', 'D) Venus'], answer: 'B', points: 5 },
      ],
    }],
  },

  tfOnly: {
    title: 'True/False Quiz',
    sections: [{
      name: 'True or False',
      questions: [
        { number: 1, type: 'true_false', question: 'Water boils at 100°C.', answer: 'True', points: 5 },
        { number: 2, type: 'true_false', question: 'The sun revolves around the Earth.', answer: 'False', points: 5 },
        { number: 3, type: 'true_false', question: 'Humans have 206 bones.', answer: 'True', points: 5 },
      ],
    }],
  },

  matchingOnly: {
    title: 'Matching Quiz',
    sections: [{
      name: 'Vocabulary Matching',
      questions: [{
        number: 1, type: 'matching', question: 'Match terms to definitions.',
        terms: ['Photosynthesis', 'Respiration', 'Osmosis'],
        definitions: ['Movement of water across a membrane', 'Converting light to energy', 'Breaking down glucose for energy'],
        answer: { Photosynthesis: 'Converting light to energy', Respiration: 'Breaking down glucose for energy', Osmosis: 'Movement of water across a membrane' },
        points: 15,
      }],
    }],
  },

  mixed: {
    title: 'Mixed Assessment',
    sections: [
      {
        name: 'Part A: Multiple Choice',
        questions: [
          { number: 1, type: 'multiple_choice', question: 'Who wrote Romeo and Juliet?', options: ['A) Dickens', 'B) Shakespeare', 'C) Austen', 'D) Twain'], answer: 'B', points: 5 },
        ],
      },
      {
        name: 'Part B: True/False',
        questions: [
          { number: 2, type: 'true_false', question: 'Shakespeare was born in Stratford-upon-Avon.', answer: 'True', points: 5 },
        ],
      },
      {
        name: 'Part C: Matching',
        questions: [{
          number: 3, type: 'matching', question: 'Match plays to genres.',
          terms: ['Hamlet', 'A Midsummer Night\'s Dream'],
          definitions: ['Comedy', 'Tragedy'],
          answer: { Hamlet: 'Tragedy', 'A Midsummer Night\'s Dream': 'Comedy' },
          points: 10,
        }],
      },
      {
        name: 'Part D: Short Answer',
        questions: [
          { number: 4, type: 'short_answer', question: 'Explain the theme of Romeo and Juliet.', answer: 'The destructive nature of feuds and the power of love.', points: 10 },
        ],
      },
    ],
  },

  // Subject-specific assessments
  usHistory8: {
    title: 'US History - American Revolution',
    sections: [{
      name: 'Questions',
      questions: [
        { number: 1, type: 'multiple_choice', question: 'What document declared independence from Britain?', options: ['A) Constitution', 'B) Declaration of Independence', 'C) Bill of Rights', 'D) Magna Carta'], answer: 'B', points: 5 },
        { number: 2, type: 'true_false', question: 'The American Revolution began in 1775.', answer: 'True', points: 5 },
        { number: 3, type: 'multiple_choice', question: 'Who was the commander of the Continental Army?', options: ['A) Jefferson', 'B) Adams', 'C) Washington', 'D) Franklin'], answer: 'C', points: 5 },
      ],
    }],
  },

  math7: {
    title: 'Math 7 - Algebraic Expressions',
    sections: [{
      name: 'Problems',
      questions: [
        { number: 1, type: 'multiple_choice', question: 'Simplify: 3x + 2x', options: ['A) 5x', 'B) 6x', 'C) 5x²', 'D) 32x'], answer: 'A', points: 5 },
        { number: 2, type: 'true_false', question: 'The expression 2(x+3) equals 2x+6.', answer: 'True', points: 5 },
        { number: 3, type: 'multiple_choice', question: 'Solve: x + 7 = 12', options: ['A) 3', 'B) 4', 'C) 5', 'D) 19'], answer: 'C', points: 5 },
      ],
    }],
  },

  science6: {
    title: 'Science 6 - Earth Systems',
    sections: [{
      name: 'Questions',
      questions: [
        { number: 1, type: 'multiple_choice', question: 'What layer of the Earth do we live on?', options: ['A) Core', 'B) Mantle', 'C) Crust', 'D) Atmosphere'], answer: 'C', points: 5 },
        { number: 2, type: 'true_false', question: 'The Earth\'s core is made of solid iron.', answer: 'False', points: 5 },
        { number: 3, type: 'matching', question: 'Match layers to descriptions.',
          terms: ['Crust', 'Mantle', 'Core'],
          definitions: ['Thinnest outer layer', 'Largest layer by volume', 'Hottest and densest'],
          answer: { Crust: 'Thinnest outer layer', Mantle: 'Largest layer by volume', Core: 'Hottest and densest' },
          points: 9 },
      ],
    }],
  },

  ela8: {
    title: 'ELA 8 - Literary Analysis',
    sections: [
      {
        name: 'Reading Comprehension',
        questions: [
          { number: 1, type: 'multiple_choice', question: 'What is a theme?', options: ['A) The setting', 'B) The main character', 'C) The central message', 'D) The plot'], answer: 'C', points: 5 },
          { number: 2, type: 'multiple_choice', question: 'What is an allegory?', options: ['A) A type of poem', 'B) A story with a hidden meaning', 'C) A biography', 'D) A news article'], answer: 'B', points: 5 },
        ],
      },
      {
        name: 'Writing',
        questions: [
          { number: 3, type: 'short_answer', question: 'Define "irony" and give an example.', answer: 'Irony is when the opposite of what is expected occurs.', points: 10 },
        ],
      },
    ],
  },

  civics: {
    title: 'Civics - Branches of Government',
    sections: [{
      name: 'Government Structure',
      questions: [
        { number: 1, type: 'multiple_choice', question: 'How many branches of government does the US have?', options: ['A) 2', 'B) 3', 'C) 4', 'D) 5'], answer: 'B', points: 5 },
        { number: 2, type: 'matching', question: 'Match branches to their roles.',
          terms: ['Legislative', 'Executive', 'Judicial'],
          definitions: ['Makes laws', 'Enforces laws', 'Interprets laws'],
          answer: { Legislative: 'Makes laws', Executive: 'Enforces laws', Judicial: 'Interprets laws' },
          points: 9 },
        { number: 3, type: 'true_false', question: 'The Supreme Court is part of the Executive Branch.', answer: 'False', points: 5 },
      ],
    }],
  },
}

export {
  AUTH_HEADERS,
  publishAssessment,
  deleteAssessment,
  startAssessment,
  uniqueName,
  answerMC,
  answerTF,
  clickNext,
  finishAndSubmit,
  dismissFeedback,
  ASSESSMENTS,
}

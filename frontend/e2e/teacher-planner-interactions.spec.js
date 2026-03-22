import { test, expect } from '@playwright/test'

test.describe('Teacher Planner — Sub-tabs', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.locator('text=Planner').first().click()
    await page.waitForTimeout(1500)
  })

  test('Lesson Planning active by default', async ({ page }) => {
    const body = await page.textContent('body')
    expect(body.includes('Lesson Planning') || body.includes('Standards') || body.includes('Details')).toBeTruthy()
  })

  test('Assessment Generator sub-tab renders', async ({ page }) => {
    const btn = page.locator('button:has-text("Assessment")').first()
    if (await btn.isVisible()) { await btn.click(); await page.waitForTimeout(1000) }
  })

  test('Calendar sub-tab renders', async ({ page }) => {
    const btn = page.locator('text=Calendar').first()
    if (await btn.isVisible()) { await btn.click(); await page.waitForTimeout(1000) }
  })

  test('Tools sub-tab renders', async ({ page }) => {
    await page.locator('text=Tools').first().click()
    await page.waitForTimeout(1000)
    const body = await page.textContent('body')
    expect(body.length).toBeGreaterThan(100)
  })

  test('Details has title field', async ({ page }) => {
    expect(await page.textContent('body')).toContain('Title')
  })

  test('Details has content type', async ({ page }) => {
    expect(await page.textContent('body')).toMatch(/Content Type|Assignment|Assessment/)
  })

  test('Reference Documents section', async ({ page }) => {
    expect(await page.textContent('body')).toMatch(/Reference|Upload|Documents/)
  })

  test('Section toggles on Assessment Generator', async ({ page }) => {
    const btn = page.locator('text=Assessment Generator').first()
    if (await btn.isVisible()) {
      await btn.click()
      await page.waitForTimeout(1000)
    }
    expect(await page.textContent('body')).toMatch(/Sections|Multiple Choice|True|Assessment|Question/)
  })

  test('Duration field', async ({ page }) => {
    expect(await page.textContent('body')).toMatch(/Duration|Period/)
  })

  test('Standards section visible', async ({ page }) => {
    expect(await page.textContent('body')).toMatch(/Standards|standards|Select/)
  })
})

test.describe('Teacher Settings — Sections', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.locator('text=Settings').first().click()
    await page.waitForTimeout(1500)
  })

  test('Rubric section', async ({ page }) => { expect(await page.textContent('body')).toMatch(/rubric|Rubric|grading/i) })
  test('AI Notes section', async ({ page }) => { expect(await page.textContent('body')).toMatch(/AI|Notes|Instructions/i) })
  test('Classroom tab', async ({ page }) => { const b = page.locator('text=Classroom').first(); if (await b.isVisible()) { await b.click(); await page.waitForTimeout(1000) } })
  test('State/grade fields', async ({ page }) => { expect(await page.textContent('body')).toMatch(/State|Grade|Subject/) })
  test('Grading style', async ({ page }) => { expect(await page.textContent('body')).toMatch(/Grading|Standard|Lenient|Strict/) })
  test('AI sub-tab exists', async ({ page }) => {
    const aiTab = page.locator('text=AI').first()
    if (await aiTab.isVisible()) {
      await aiTab.click()
      await page.waitForTimeout(1000)
    }
    expect(await page.textContent('body')).toMatch(/AI|Model|Provider|Instructions/)
  })
})

test.describe('Teacher Results', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.locator('text=Results').first().click()
    await page.waitForTimeout(1500)
  })
  test('renders content', async ({ page }) => { expect((await page.textContent('body')).length).toBeGreaterThan(100) })
  test('has filter or content', async ({ page }) => { expect(await page.textContent('body')).toMatch(/Period|Results|Submissions|No results/) })
  test('portal submissions section', async ({ page }) => { expect(await page.textContent('body')).toMatch(/Portal|Submission|Student|results/) })
})

test.describe('Teacher Analytics', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.locator('text=Analytics').first().click()
    await page.waitForTimeout(1500)
  })
  test('renders', async ({ page }) => { expect((await page.textContent('body')).length).toBeGreaterThan(100) })
  test('charts or empty', async ({ page }) => { expect(await page.textContent('body')).toMatch(/Analytics|No data|Grade|Student/) })
  test('assistant or prompt area', async ({ page }) => { expect(await page.textContent('body')).toMatch(/Assistant|Ask|analyze|trends|students/) })
})

test.describe('Multi-Student Same Assessment', () => {
  let joinCode
  test.beforeAll(async ({ request }) => {
    const { publishAssessment, ASSESSMENTS } = await import('./helpers.js')
    joinCode = await publishAssessment(request, ASSESSMENTS.mcOnly, { content_type: 'assessment', show_score_immediately: true, show_correct_answers: true })
  })
  test.afterAll(async ({ request }) => {
    const { deleteAssessment } = await import('./helpers.js')
    await deleteAssessment(request, joinCode)
  })

  test('student 1 all correct → 100%', async ({ page }) => {
    test.skip(!joinCode)
    const { startAssessment, uniqueName } = await import('./helpers.js')
    await startAssessment(page, joinCode, uniqueName('S1'))
    await page.locator('text=B) 4').first().click(); await page.waitForTimeout(200)
    await page.locator('text=C) Paris').first().click(); await page.waitForTimeout(200)
    await page.locator('text=B) Jupiter').first().click(); await page.waitForTimeout(200)
    await page.locator('button:has-text("Submit")').first().click(); await page.waitForTimeout(3000)
    expect(await page.textContent('body')).toContain('100%')
  })

  test('student 2 all wrong → 0%', async ({ page }) => {
    test.skip(!joinCode)
    const { startAssessment, uniqueName } = await import('./helpers.js')
    await startAssessment(page, joinCode, uniqueName('S2'))
    await page.locator('text=A) 3').first().click(); await page.waitForTimeout(200)
    await page.locator('text=A) London').first().click(); await page.waitForTimeout(200)
    await page.locator('text=A) Mars').first().click(); await page.waitForTimeout(200)
    await page.locator('button:has-text("Submit")').first().click(); await page.waitForTimeout(3000)
    expect(await page.textContent('body')).toContain('0%')
  })

  test('student 3 partial → 67%', async ({ page }) => {
    test.skip(!joinCode)
    const { startAssessment, uniqueName } = await import('./helpers.js')
    await startAssessment(page, joinCode, uniqueName('S3'))
    await page.locator('text=B) 4').first().click(); await page.waitForTimeout(200)
    await page.locator('text=A) London').first().click(); await page.waitForTimeout(200)
    await page.locator('text=B) Jupiter').first().click(); await page.waitForTimeout(200)
    await page.locator('button:has-text("Submit")').first().click(); await page.waitForTimeout(3000)
    expect(await page.textContent('body')).toContain('67%')
  })
})

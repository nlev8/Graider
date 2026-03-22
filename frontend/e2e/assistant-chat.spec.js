/**
 * AI Assistant / Chat feature E2E tests.
 *
 * Tests the AssistantChat component UI rendering and the assistant API
 * endpoints. Because the assistant depends on external AI APIs (Anthropic,
 * OpenAI, Gemini), these tests do NOT exercise actual AI responses — they
 * verify that UI elements exist and that endpoints respond with the
 * expected shape (even if with errors due to missing API keys).
 *
 * Prerequisites: Server running at localhost:3000 in dev mode
 * (FLASK_ENV=development, which auto-authenticates as local-dev teacher).
 *
 * @tags @assistant
 */
import { test, expect } from '@playwright/test'
import { AUTH_HEADERS } from './helpers.js'

// ══════════════════════════════════════════
// UI RENDERING TESTS
// ══════════════════════════════════════════

test.describe('Assistant Chat — UI', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    // Navigate to the Assistant tab
    const assistantTab = page.locator('nav button', { hasText: 'Assistant' })
    if (await assistantTab.isVisible({ timeout: 5000 })) {
      await assistantTab.click()
      await page.waitForTimeout(500)
    }
  })

  test('assistant tab renders with header', async ({ page }) => {
    // The AssistantChat component renders a "Graider Assistant" heading
    const heading = page.locator('text=Graider Assistant')
    await expect(heading).toBeVisible({ timeout: 5000 })
  })

  test('chat input textarea and send button exist', async ({ page }) => {
    // Textarea for typing messages
    const textarea = page.locator('textarea[placeholder*="Ask about"]')
    await expect(textarea).toBeVisible({ timeout: 5000 })
    await expect(textarea).toBeEnabled()

    // Send button (round button with Send icon at the bottom of the chat)
    const sendButton = page.locator('button[title="Send message"]')
    await expect(sendButton).toBeVisible()
  })

  test('suggested prompts are visible in empty state', async ({ page }) => {
    // When no messages exist, the assistant shows suggested prompt buttons
    const emptyStateText = page.locator('text=Ask about your students')
    await expect(emptyStateText).toBeVisible({ timeout: 5000 })

    // At least one suggested prompt should be visible
    const promptButton = page.locator('button', { hasText: 'What caused the low grades' })
    await expect(promptButton).toBeVisible()
  })

  test('clear memory button is present', async ({ page }) => {
    const clearMemoryBtn = page.locator('button', { hasText: 'Clear Memory' })
    await expect(clearMemoryBtn).toBeVisible({ timeout: 5000 })
  })

  test('file attach button exists', async ({ page }) => {
    const attachBtn = page.locator('button[title="Attach file (image, PDF, or DOCX)"]')
    await expect(attachBtn).toBeVisible({ timeout: 5000 })
  })
})

// ══════════════════════════════════════════
// API ENDPOINT SMOKE TESTS
// ══════════════════════════════════════════

test.describe('Assistant Chat — API Endpoints', () => {

  test('POST /api/assistant/chat returns response (may error without API key)', async ({ request }) => {
    const response = await request.post('/api/assistant/chat', {
      headers: AUTH_HEADERS,
      data: {
        messages: [{ role: 'user', content: 'Hello' }],
        session_id: 'playwright-test-session',
      },
    })
    // Either 200 (streaming) or 500 (no API key) — both are valid
    expect([200, 500]).toContain(response.status())
    if (response.status() === 500) {
      const body = await response.json()
      // Should be a structured error, not a crash
      expect(body).toHaveProperty('error')
    }
  })

  test('POST /api/assistant/clear returns success', async ({ request }) => {
    const response = await request.post('/api/assistant/clear', {
      headers: AUTH_HEADERS,
      data: { session_id: 'playwright-test-session' },
    })
    expect(response.status()).toBe(200)
    const body = await response.json()
    expect(body.status).toBe('cleared')
  })

  test('GET /api/assistant/costs returns cost structure', async ({ request }) => {
    const response = await request.get('/api/assistant/costs', {
      headers: AUTH_HEADERS,
    })
    expect(response.status()).toBe(200)
    const body = await response.json()
    // Should have total and daily keys (even if zeros)
    expect(body).toHaveProperty('total')
    expect(body.total).toHaveProperty('total_cost')
  })

  test('GET /api/assistant/memory returns memories array', async ({ request }) => {
    const response = await request.get('/api/assistant/memory', {
      headers: AUTH_HEADERS,
    })
    expect(response.status()).toBe(200)
    const body = await response.json()
    expect(body).toHaveProperty('memories')
    expect(body).toHaveProperty('count')
    expect(Array.isArray(body.memories)).toBeTruthy()
  })

  test('GET /api/assistant/voice-config returns config object', async ({ request }) => {
    const response = await request.get('/api/assistant/voice-config', {
      headers: AUTH_HEADERS,
    })
    expect(response.status()).toBe(200)
    const body = await response.json()
    expect(body).toHaveProperty('enabled')
    expect(body).toHaveProperty('voice')
  })

  test('POST /api/assistant/cancel returns success', async ({ request }) => {
    const response = await request.post('/api/assistant/cancel', {
      headers: AUTH_HEADERS,
      data: { session_id: 'playwright-test-session' },
    })
    expect(response.status()).toBe(200)
    const body = await response.json()
    expect(body.status).toBe('cancelled')
  })

  test('POST /api/assistant/chat rejects empty messages', async ({ request }) => {
    const response = await request.post('/api/assistant/chat', {
      headers: AUTH_HEADERS,
      data: { messages: [] },
    })
    // Should return 400 for missing/empty messages (or 500 if API key check runs first)
    expect([400, 500]).toContain(response.status())
    const body = await response.json()
    expect(body).toHaveProperty('error')
  })
})

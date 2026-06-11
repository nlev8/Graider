/**
 * App-boundary XSS contract for AssistantChat
 *
 * Closes GH #229 (filed during PR #228 Codex review): the smoke-level
 * DOMPurify contract tests in `smoke.test.jsx` verify the LIBRARY
 * behavior in jsdom but don't exercise the actual production call site
 * (since the CQ wave-3 split: `assistant-chat/markdown.js`, rendered by
 * `assistant-chat/MessageBubble.jsx`) where `renderMarkdown` pipes
 * assistant messages through `DOMPurify.sanitize()` and then drops them
 * into a `dangerouslySetInnerHTML` block.
 *
 * This test renders AssistantChat with a malicious assistant message
 * seeded via the localStorage hydration path used by `loadStoredMessages`
 * (since the split: `assistant-chat/storage.js`), then asserts the
 * rendered DOM contains:
 *   - NO `<script>` element
 *   - NO inline `onerror`/`onclick`/etc. handler attributes
 *   - NO `javascript:` URI in `href` attributes
 *   - NO global side effect from any embedded payload
 */
import React from 'react'
import { render } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// DOMPurify intentionally NOT mocked — the whole point of this test is
// to verify the REAL sanitizer in the actual render path.

// Mock api so the AssistantChat component doesn't try to call the
// backend during render.
vi.mock('../services/api', () => ({
  default: {},
  getAuthHeaders: vi.fn().mockReturnValue({}),
  fetchApi: vi.fn().mockResolvedValue({}),
}))

// Mock the voice hook — it touches navigator.mediaDevices which jsdom
// doesn't ship and which is irrelevant to this test's scope.
vi.mock('../hooks/useVoice', () => ({
  useVoice: () => ({
    isListening: false,
    isSpeaking: false,
    startListening: vi.fn(),
    stopListening: vi.fn(),
    speak: vi.fn(),
    stopSpeaking: vi.fn(),
    error: null,
  }),
}))

const STORAGE_KEY_MESSAGES = 'graider_assistant_messages'

// Seed a malicious assistant message via the same localStorage path
// `loadStoredMessages` reads on mount.
function seedMessages(messages) {
  localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify(messages))
}

// jsdom doesn't implement Element.prototype.scrollIntoView; the
// component calls it inside a useEffect after mount. Stub before any
// render so React's effect runner doesn't throw.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn()
}

describe('AssistantChat — app-boundary XSS contract', () => {
  beforeEach(() => {
    localStorage.clear()
    // Ensure the global side-effect canary is unset before each test.
    delete window.__pwn_assistant_chat
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('strips <script> tags from assistant message content', async () => {
    const dirty = '<script>window.__pwn_assistant_chat = "leaked"</script>safe text'
    seedMessages([{ role: 'assistant', content: dirty }])

    const AssistantChat = (await import('../components/AssistantChat')).default
    const { container } = render(
      React.createElement(AssistantChat, { addToast: vi.fn(), subject: 'math' })
    )

    // Most important: jsdom must not have executed the script payload.
    expect(window.__pwn_assistant_chat).toBeUndefined()

    // The literal <script> tag must not appear in the rendered DOM.
    expect(container.querySelector('script')).toBeNull()

    // Belt-and-suspenders: the raw payload bytes must not appear in
    // the innerHTML either (catches a future regression where
    // DOMPurify is bypassed but jsdom doesn't execute the script for
    // some other reason).
    expect(container.innerHTML).not.toContain('window.__pwn_assistant_chat')
  })

  it('strips inline event handlers (onerror, onclick) from assistant content', async () => {
    const dirty = (
      '<img src=x onerror="window.__pwn_assistant_chat=1">'
      + '<a href="#" onclick="window.__pwn_assistant_chat=2">click</a>'
    )
    seedMessages([{ role: 'assistant', content: dirty }])

    const AssistantChat = (await import('../components/AssistantChat')).default
    const { container } = render(
      React.createElement(AssistantChat, { addToast: vi.fn(), subject: 'math' })
    )

    expect(window.__pwn_assistant_chat).toBeUndefined()
    // No element should retain an onerror/onclick attribute after
    // sanitization.
    expect(container.innerHTML).not.toMatch(/\bonerror\s*=/i)
    expect(container.innerHTML).not.toMatch(/\bonclick\s*=/i)
  })

  it('strips javascript: URIs from href attributes', async () => {
    const dirty = '<a href="javascript:window.__pwn_assistant_chat=3">click me</a>'
    seedMessages([{ role: 'assistant', content: dirty }])

    const AssistantChat = (await import('../components/AssistantChat')).default
    const { container } = render(
      React.createElement(AssistantChat, { addToast: vi.fn(), subject: 'math' })
    )

    expect(window.__pwn_assistant_chat).toBeUndefined()
    // No href containing javascript: should survive sanitization.
    const anchors = container.querySelectorAll('a[href]')
    for (const a of anchors) {
      expect(a.getAttribute('href') || '').not.toMatch(/^javascript:/i)
    }
  })

  it('preserves benign markdown in assistant content', async () => {
    // Sanity: the sanitizer should NOT over-strip legitimate output.
    // If this fails, future devs who tighten DOMPurify config will know
    // they broke the assistant's normal rendering.
    const safe = 'Here is **bold** and *italic* and `code` text.'
    seedMessages([{ role: 'assistant', content: safe }])

    const AssistantChat = (await import('../components/AssistantChat')).default
    const { container } = render(
      React.createElement(AssistantChat, { addToast: vi.fn(), subject: 'math' })
    )

    // renderMarkdown converts ** → <strong>, * → <em>, ` → <code>
    expect(container.innerHTML).toContain('<strong>bold</strong>')
    expect(container.innerHTML).toContain('<em>italic</em>')
    expect(container.innerHTML).toContain('<code')
    expect(container.innerHTML).toContain('code')
  })

  it('mock detection: a known-bad payload MUST be sanitized in the rendered DOM', async () => {
    // Belt-and-suspenders against a future PR that re-introduces a
    // DOMPurify identity mock for this suite. The unsanitized content
    // would survive and contain the literal string "window.__pwn".
    const dirty = '<script>window.__pwn_assistant_chat=4</script>'
    seedMessages([{ role: 'assistant', content: dirty }])

    const AssistantChat = (await import('../components/AssistantChat')).default
    const { container } = render(
      React.createElement(AssistantChat, { addToast: vi.fn(), subject: 'math' })
    )

    // If DOMPurify were mocked as identity, the script tag bytes would
    // appear verbatim in innerHTML. They must not.
    expect(container.innerHTML).not.toContain('<script>')
    expect(window.__pwn_assistant_chat).toBeUndefined()
  })
})

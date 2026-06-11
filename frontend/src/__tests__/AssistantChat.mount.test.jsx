import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Render-time smoke test for AssistantChat. Added with the CQ wave-3 split of
// AssistantChat.jsx into assistant-chat/* (mirrors AnalyticsTab.mount.test.jsx,
// added with the wave-1 tabs/analytics split, for the same reason): before this
// test, the only renderer of AssistantChat was the XSS contract suite, which
// asserts sanitization — not that the full extracted tree (hook, header, empty
// state, message bubbles, attachment chips, input row) actually mounts with
// real content. Build + unit tests pass even if a split leaves an unimported
// component or mis-threaded prop that white-screens the tab at runtime.

// Mock api so the component doesn't call the backend during render.
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

// jsdom doesn't implement Element.prototype.scrollIntoView; the hook calls it
// inside a useEffect after mount.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn()
}

describe('AssistantChat mounts without crashing (render-time smoke)', () => {
  beforeEach(() => {
    localStorage.clear()
  })
  afterEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('renders header, empty-state suggestions, and input row with no messages', async () => {
    const AssistantChat = (await import('../components/AssistantChat')).default
    render(
      React.createElement(AssistantChat, { addToast: vi.fn(), subject: 'Science' })
    )

    // ChatHeader
    expect(screen.getByText('Graider Assistant')).toBeTruthy()
    expect(screen.getByText('Clear Memory')).toBeTruthy()
    // EmptyState — subject-specific suggested prompt (Science) + shared one
    expect(screen.getByText('Ask about your students')).toBeTruthy()
    expect(screen.getByText('Grade this lab data table against the answer key')).toBeTruthy()
    expect(screen.getByText('Which students need attention?')).toBeTruthy()
    expect(screen.getByText('More ideas')).toBeTruthy()
    // ChatInput
    expect(screen.getByPlaceholderText('Ask about grades, students, or assignments...')).toBeTruthy()
  })

  it('renders message bubbles with tool chips, download button, and cost', async () => {
    // Seed via the same localStorage hydration path loadStoredMessages reads
    // on mount (XSS-suite precedent).
    localStorage.setItem(STORAGE_KEY_MESSAGES, JSON.stringify([
      { role: 'user', content: 'Show me the class average' },
      {
        role: 'assistant',
        content: 'Here is the **average**.',
        toolCalls: [{ id: 't1', tool: 'query_grades', status: 'done' }],
        downloadUrl: '/api/download-worksheet/abc',
        downloadFilename: 'report.csv',
        cost: { total_cost: 0.0123, tts_cost: 0 },
      },
    ]))

    const AssistantChat = (await import('../components/AssistantChat')).default
    const { container } = render(
      React.createElement(AssistantChat, { addToast: vi.fn(), subject: null })
    )

    // MessageBubble: user text, tool chip past-tense label, download button,
    // rendered markdown, per-message cost line.
    expect(screen.getByText('Show me the class average')).toBeTruthy()
    expect(screen.getByText('Queried grades')).toBeTruthy()
    expect(screen.getByText('Download report.csv')).toBeTruthy()
    expect(container.innerHTML).toContain('<strong>average</strong>')
    expect(screen.getByText(/\$0\.0123/)).toBeTruthy()
    // With messages present, the EmptyState early-returns null.
    expect(screen.queryByText('Ask about your students')).toBeNull()
    // Header gains the Clear Chat button once messages exist.
    expect(screen.getByText('Clear Chat')).toBeTruthy()
  })
})

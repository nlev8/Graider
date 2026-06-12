import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'

// Render-time smoke test for BehaviorPanel. Added with the CQ wave-8 split
// of BehaviorPanel.jsx into behavior-panel/* (mirrors
// TutorialOverlay.mount.test.jsx from the wave-7 split, for the same
// reason): build + unit tests pass even if a split leaves an unimported
// component or mis-threaded prop that white-screens the panel at runtime.
// This asserts real content (collapsed tab, header, filters, student rows
// with counts, expanded event detail) renders through the shell ->
// CollapsedTab/PanelHeader/BehaviorFilters/StudentList/StudentEventDetail
// chain, and that the behavior-email-request dispatch (consumed by
// assistant-chat's useAssistantChat listener) still fires from the moved
// mail button.

const { loadCumulative } = vi.hoisted(() => ({ loadCumulative: vi.fn() }))

vi.mock('../hooks/useBehaviorStore', () => ({
  useBehaviorStore: () => ({
    state: {
      cumulativeData: {
        'Ada Lovelace': { name: 'Ada Lovelace', total_corrections: 3, total_praise: 1 },
        'Alan Turing': { name: 'Alan Turing', total_corrections: 1, total_praise: 4 },
      },
      loading: false,
      error: null,
    },
    loadCumulative,
  }),
}))

vi.mock('../services/api', () => ({
  getAuthHeaders: vi.fn(async () => ({})),
}))

import BehaviorPanel from '../components/BehaviorPanel'

afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

const expandPanel = (container) => {
  // Collapsed edge tab first (shell owns the collapsed flag).
  const tab = container.querySelector('[title="Behavior Tracking"]')
  expect(tab).toBeTruthy()
  fireEvent.click(tab)
}

describe('BehaviorPanel mounts without crashing (render-time smoke)', () => {
  it('renders collapsed tab, then expanded header, filters, and student rows with counts', () => {
    const { container } = render(<BehaviorPanel addToast={vi.fn()} />)

    expandPanel(container)

    // Header + filters through PanelHeader / BehaviorFilters.
    expect(screen.getByText('Behavior')).toBeTruthy()
    expect(screen.getByPlaceholderText('Filter by period')).toBeTruthy()

    // Student rows through StudentList, sorted by corrections desc.
    expect(screen.getByText('Ada Lovelace')).toBeTruthy()
    expect(screen.getByText('Alan Turing')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy() // Ada corrections
    expect(screen.getByText('4')).toBeTruthy() // Alan praise

    // Shell effect ran with the (empty) filter state.
    expect(loadCumulative).toHaveBeenCalledWith({ period: '', date_from: '', date_to: '' })
  })

  it('expands a student row and renders fetched event detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      json: async () => ({
        status: 'success',
        data: {
          events: [{
            id: 1, type: 'correction', note: 'Talking during quiz',
            date: '2026-06-10', event_time: '2026-06-10T10:00:00Z', source: 'stt',
          }],
        },
      }),
    })))

    const { container } = render(<BehaviorPanel addToast={vi.fn()} />)
    expandPanel(container)

    fireEvent.click(screen.getByText('Ada Lovelace'))

    // Event detail through StudentEventDetail (type badge, source badge, note).
    expect(await screen.findByText('Talking during quiz')).toBeTruthy()
    expect(screen.getByText('correction')).toBeTruthy()
    expect(screen.getByText('stt')).toBeTruthy()
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/behavior/events?student_name=Ada+Lovelace'),
      expect.any(Object),
    )
  })

  it('mail button dispatches behavior-email-request and toasts', async () => {
    const addToast = vi.fn()
    const handler = vi.fn()
    window.addEventListener('behavior-email-request', handler)
    try {
      const { container } = render(<BehaviorPanel addToast={addToast} />)
      expandPanel(container)

      fireEvent.click(container.querySelector('[title="Generate email for Ada Lovelace"]'))

      await waitFor(() => expect(handler).toHaveBeenCalledTimes(1))
      expect(handler.mock.calls[0][0].detail).toEqual({
        message: 'Generate a behavior email for Ada Lovelace',
      })
      expect(addToast).toHaveBeenCalledWith('Email request sent to assistant', 'info')
    } finally {
      window.removeEventListener('behavior-email-request', handler)
    }
  })
})

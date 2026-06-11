import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import PlannerTools from '../components/PlannerTools'

// Content-asserting mount test for PlannerTools. Added with the CQ wave-5
// split of PlannerTools.jsx into planner-tools/* (mirrors
// AssistantChat.mount.test.jsx / AnalyticsTab.mount.test.jsx from earlier
// waves, for the same reason): the pre-existing PlannerTools.test.jsx smoke
// test renders the shell, but build + smoke pass even if a split leaves an
// unimported card or mis-threaded prop that blanks one tool at runtime.
// This test asserts real content from each of the four extracted cards.

// Mock api so the cards don't call the backend during render.
vi.mock('../services/api', () => ({
  adjustReadingLevel: vi.fn().mockResolvedValue({ adjusted_text: 'x', reading_level_estimate: '6' }),
  extractTextFromFile: vi.fn().mockResolvedValue({ text: '' }),
  listResources: vi.fn().mockResolvedValue({ resources: [] }),
  loadResource: vi.fn().mockResolvedValue({ resource: {} }),
  saveResource: vi.fn().mockResolvedValue({ status: 'saved' }),
}))

const makeProps = (overrides = {}) => ({
  config: { subject: 'Math', grade: '8', globalAINotes: '' },
  lessonPlan: null,
  generatedAssignment: null,
  globalAINotes: '',
  uploadedDocs: [],
  addToast: vi.fn(),
  shareWithClass: vi.fn(),
  ...overrides,
})

describe('PlannerTools mounts all four tool cards (content-asserting)', () => {
  it('renders the heading and a distinctive control from every extracted card', () => {
    render(<PlannerTools {...makeProps()} />)

    // ReadingLevelAdjuster
    expect(screen.getByText('Reading Level Adjuster')).toBeTruthy()
    expect(screen.getByPlaceholderText(/Paste text here or upload documents/)).toBeTruthy()
    expect(screen.getByText('Target Level')).toBeTruthy()

    // StudyGuideGenerator
    expect(screen.getByText('Study Guide Generator')).toBeTruthy()
    expect(screen.getByText(/Generate Study Guide/)).toBeTruthy()

    // FlashcardGenerator
    expect(screen.getByText('Flashcard Generator')).toBeTruthy()
    expect(screen.getByText(/Generate Flashcards/)).toBeTruthy()
    expect(screen.getByPlaceholderText(/Focus on Chapter 5 vocabulary only/)).toBeTruthy()

    // SlideDeckGenerator
    expect(screen.getByText('Slide Deck Generator')).toBeTruthy()
    expect(screen.getByText(/Generate Slide Deck/)).toBeTruthy()
    expect(screen.getByText('AI Graphics')).toBeTruthy()
  })

  it('generate buttons are disabled with no lesson plan / assignment / docs (pre-split behavior)', () => {
    render(<PlannerTools {...makeProps()} />)
    expect(screen.getByText(/Generate Study Guide/).closest('button').disabled).toBe(true)
    expect(screen.getByText(/Generate Flashcards/).closest('button').disabled).toBe(true)
    expect(screen.getByText(/Generate Slide Deck/).closest('button').disabled).toBe(true)
  })
})

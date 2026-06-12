import React from 'react'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import MatchingCards from '../components/MatchingCards'

// Render-time smoke + interaction test for MatchingCards. Added with the CQ
// wave-8 split of MatchingCards.jsx into matching-cards/* (mirrors
// TutorialOverlay.mount.test.jsx from the wave-7 split, for the same reason):
// build + unit tests pass even if a split leaves an unimported component or
// mis-threaded prop that white-screens the card grid at runtime. Asserts real
// content renders through the shell -> TermsColumn / DefinitionsColumn chain,
// and pins the match-state contract the student portal e2e depends on:
// correct pair -> onMatch(newMatched, shuffledDefs) after the 600ms success
// animation; wrong pair -> shake + reset, no onMatch.

const baseProps = () => ({
  terms: ['Cat', 'Dog'],
  definitions: ['Feline', 'Canine'],
  correctAnswer: { Cat: 'Feline', Dog: 'Canine' },
  onMatch: vi.fn(),
})

describe('MatchingCards mounts without crashing (render-time smoke)', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('renders column headers, terms, definitions, and instructions through the extracted columns', () => {
    render(React.createElement(MatchingCards, baseProps()))
    expect(screen.getByText('Terms')).toBeTruthy()
    expect(screen.getByText('Definitions')).toBeTruthy()
    expect(screen.getByText('Cat')).toBeTruthy()
    expect(screen.getByText('Dog')).toBeTruthy()
    expect(screen.getByText('Feline')).toBeTruthy()
    expect(screen.getByText('Canine')).toBeTruthy()
    expect(screen.getByText(/Click a term, then click its matching definition/)).toBeTruthy()
  })

  it('correct pair calls onMatch with the new matches and shuffledDefs after the 600ms animation', () => {
    vi.useFakeTimers()
    const props = baseProps()
    render(React.createElement(MatchingCards, props))

    fireEvent.click(screen.getByText('Cat'))
    fireEvent.click(screen.getByText('Feline'))
    expect(props.onMatch).not.toHaveBeenCalled() // success animation pending

    act(() => {
      vi.advanceTimersByTime(600)
    })
    expect(props.onMatch).toHaveBeenCalledTimes(1)
    const [matches, shuffledDefs] = props.onMatch.mock.calls[0]
    // Term 0 (Cat) is matched, and the shuffled index it stores maps back to
    // original definition 0 (Feline) — the contract AnswerArea /
    // QuestionAnswerInputs use to write `...-match-N` answer keys.
    expect(matches[0]).toBeDefined()
    expect(shuffledDefs[matches[0]].originalIdx).toBe(0)
  })

  it('wrong pair shakes and resets without calling onMatch', () => {
    vi.useFakeTimers()
    const props = baseProps()
    render(React.createElement(MatchingCards, props))

    fireEvent.click(screen.getByText('Cat'))
    fireEvent.click(screen.getByText('Canine'))
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(props.onMatch).not.toHaveBeenCalled()
  })

  it('readOnly ignores clicks entirely', () => {
    vi.useFakeTimers()
    const props = { ...baseProps(), readOnly: true }
    render(React.createElement(MatchingCards, props))

    fireEvent.click(screen.getByText('Cat'))
    fireEvent.click(screen.getByText('Feline'))
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(props.onMatch).not.toHaveBeenCalled()
  })

  it('showAnswers marks everything matched and shows the completion banner', () => {
    render(React.createElement(MatchingCards, { ...baseProps(), showAnswers: true }))
    expect(screen.getByText(/All terms matched correctly!/)).toBeTruthy()
  })

  it('initializes from existingMatches (matched term shows the checkmark badge)', () => {
    const { container } = render(
      React.createElement(MatchingCards, { ...baseProps(), existingMatches: { 0: 0 } })
    )
    expect(container.textContent).toContain(String.fromCharCode(10003))
  })
})

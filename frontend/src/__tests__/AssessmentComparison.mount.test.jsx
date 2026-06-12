import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'

// Render-time smoke test for AssessmentComparison. Added with the CQ wave-8
// split of AssessmentComparison.jsx into assessment-comparison/* (mirrors
// TutorialOverlay.mount.test.jsx from the wave-7 split, for the same
// reason): build + unit tests pass even if a split leaves an unimported
// component or mis-threaded prop that white-screens the tab at runtime.
// This asserts real content (picker chips, stat cards, box plot SVG,
// standards heatmap incl. the red-cell remediation trigger) renders through
// the shell -> AssessmentPicker / ComparisonResults -> BoxPlotRow /
// StandardsHeatmap chain.

const { getClassGradebook, getClassAssessmentComparison } = vi.hoisted(() => ({
  getClassGradebook: vi.fn(),
  getClassAssessmentComparison: vi.fn(),
}))

vi.mock('../services/api', () => ({
  getClassGradebook,
  getClassAssessmentComparison,
}))

// Not part of the split; stub so the drawer mount is observable without
// pulling its full dependency tree into this smoke test.
vi.mock('../tabs/RemediationDrawer', () => ({
  default: (props) => <div data-testid="remediation-drawer">{props.standardCode}</div>,
}))

import AssessmentComparison from '../tabs/AssessmentComparison'

const GRADEBOOK = {
  assessments: [
    { content_id: 'c1', title: 'Quiz One', content_type: 'assessment' },
    { content_id: 'c2', title: 'Quiz Two', content_type: 'assessment' },
    { content_id: 'c3', title: 'Worksheet', content_type: 'assignment' }, // filtered out
  ],
}

const COMPARISON = {
  class_roster_size: 4,
  assessments: [
    {
      content_id: 'c1', title: 'Quiz One', n: 4, mean: 88, median: 90,
      min: 70, max: 98, q1: 82, q3: 94, submission_rate: 1, max_points: 10,
    },
    {
      content_id: 'c2', title: 'Quiz Two', n: 0, mean: null,
      submission_rate: 0, max_points: 5,
    },
  ],
  standards_matrix: {
    standards: ['TEKS.8.1A'],
    cells: { c1: { 'TEKS.8.1A': { percentage: 65, students_assessed: 4 } } },
  },
}

afterEach(() => {
  vi.clearAllMocks()
})

const selectTwo = async () => {
  getClassGradebook.mockResolvedValue(GRADEBOOK)
  getClassAssessmentComparison.mockResolvedValue(COMPARISON)
  const utils = render(<AssessmentComparison classId="class-1" />)
  fireEvent.click(await screen.findByText('Quiz One'))
  fireEvent.click(screen.getByText('Quiz Two'))
  return utils
}

describe('AssessmentComparison mounts without crashing (render-time smoke)', () => {
  it('renders heading + picker chips (assessments only) after bootstrap', async () => {
    getClassGradebook.mockResolvedValue(GRADEBOOK)
    render(<AssessmentComparison classId="class-1" />)

    expect(await screen.findByText('Compare Assessments')).toBeTruthy()
    expect(screen.getByText('Quiz One')).toBeTruthy()
    expect(screen.getByText('Quiz Two')).toBeTruthy()
    // content_type='assignment' rows never reach the picker.
    expect(screen.queryByText('Worksheet')).toBeNull()
    expect(screen.getByPlaceholderText('Search assessments...')).toBeTruthy()
    expect(screen.getByText('Pick at least 2 assessments to compare.')).toBeTruthy()
    expect(getClassGradebook).toHaveBeenCalledWith('class-1', 'latest')
  })

  it('selecting 2 renders stat cards, box plot SVG, and standards heatmap', async () => {
    const { container } = await selectTwo()

    // Stat cards through ComparisonResults.
    expect(await screen.findByText('88%')).toBeTruthy()
    expect(screen.getByText('No submissions yet')).toBeTruthy()
    expect(screen.getByText(/4 of 4/)).toBeTruthy()
    expect(screen.getByText(/Max points: 10/)).toBeTruthy()

    // Box plot through BoxPlotRow (one box for c1, "no data" slot for c2).
    expect(screen.getByText('Score distribution')).toBeTruthy()
    expect(container.querySelector('svg rect')).toBeTruthy()
    expect(screen.getByText('no data')).toBeTruthy()

    // Standards heatmap through StandardsHeatmap: red cell is a keyboard-
    // reachable trigger; the not-covered c2 cell renders the em-dash label.
    expect(screen.getByText('Standards coverage')).toBeTruthy()
    expect(screen.getByText('TEKS.8.1A')).toBeTruthy()
    const redCell = screen.getByText('65%')
    expect(redCell.getAttribute('role')).toBe('button')

    expect(getClassAssessmentComparison).toHaveBeenCalledWith('class-1', ['c1', 'c2'], 'latest')
  })

  it('clicking a red heatmap cell mounts the remediation drawer for that standard', async () => {
    await selectTwo()

    fireEvent.click(await screen.findByText('65%'))

    const drawer = await screen.findByTestId('remediation-drawer')
    expect(drawer.textContent).toBe('TEKS.8.1A')
  })
})

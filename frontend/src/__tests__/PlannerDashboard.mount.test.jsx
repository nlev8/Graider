import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import PlannerDashboard from '../components/PlannerDashboard'

// Content-asserting mount test for PlannerDashboard. Added with the CQ wave-7
// split of PlannerDashboard.jsx into planner-dashboard/* (mirrors
// PlannerTools.mount.test.jsx / StudentPortal.mount.test.jsx from earlier
// waves, for the same reason): the pre-existing PlannerDashboard.test.jsx
// smoke test renders the shell with empty data, but build + smoke pass even
// if the split leaves an unimported card or a mis-threaded prop that blanks
// a section at runtime. This test populates every section and asserts real
// content from each of the seven extracted components.

// Mock api so InProgressDraftsCard's end-attempt handler doesn't reach the
// backend (it is only invoked on click, but mocking keeps the module inert).
vi.mock('../services/api', () => ({
  endStudentAttempt: vi.fn().mockResolvedValue({ success: true }),
}))

const makeProps = (overrides = {}) => ({
  // data
  allTeacherTags: ['unit-1'],
  contentSubmissionsGroups: [
    { student_id: 'st1', student_name: 'Ada Lovelace', attempts: [{}, {}] },
  ],
  inProgressDrafts: [
    { submission_id: 's1', student_name: 'Grace Hopper', answered_count: 4, elapsed_seconds: 300 },
  ],
  loadingPublished: false,
  loadingResults: false,
  loadingSavedAssessments: false,
  loadingSharedResources: false,
  publishedAssessments: [
    { join_code: 'ABC123', title: 'Quiz 1', content_type: 'assessment', is_active: true, submission_count: 2, created_at: '2026-06-01T00:00:00Z' },
    { join_code: 'DEF456', title: 'HW 2', content_type: 'assignment', is_active: false, submission_count: 0, created_at: '2026-06-02T00:00:00Z' },
  ],
  savedAssessments: [
    { filename: 'f1.json', name: 'Saved Quiz', question_count: 5, total_points: 20, saved_at: '2026-06-03T00:00:00Z' },
  ],
  selectedAssessmentResults: {
    joinCode: 'ABC123',
    title: 'Quiz 1 Results',
    submissions: [
      {
        student_id: 'st1',
        student_name: 'Ada Lovelace',
        percentage: 90,
        score: 9,
        total_points: 10,
        submitted_at: '2026-06-01T12:00:00Z',
        results: { standards_mastery: { 'CCSS.1': { points_earned: 9, points_possible: 10, question_count: 3 } } },
      },
    ],
  },
  selectedTagFilter: 'all',
  sharedResources: [
    { id: 'r1', content_type: 'flashcards', title: 'Unit 1 Cards', class_name: 'Period 1', created_at: '2026-06-01T00:00:00Z' },
  ],
  teacherClasses: [
    { id: 1, name: 'Period 1', join_code: 'JC1234', subject: 'History', class_students: [{ count: 23 }] },
  ],
  // handlers
  addToast: vi.fn(),
  deletePublishedAssessment: vi.fn(),
  deleteSavedAssessment: vi.fn(),
  fetchAssessmentResults: vi.fn(),
  fetchPublishedAssessments: vi.fn(),
  fetchSavedAssessments: vi.fn(),
  fetchSharedResources: vi.fn(),
  fetchTeacherClasses: vi.fn(),
  fetchTeacherTags: vi.fn(),
  handleDeleteAllSharedResources: vi.fn(),
  handleDeleteSharedResource: vi.fn(),
  itemMatchesTagFilter: vi.fn().mockReturnValue(true),
  loadSavedAssessment: vi.fn(),
  toggleAssessmentStatus: vi.fn(),
  renderTagRow: vi.fn(() => null),
  // setters (forwarded)
  setAttemptDrawerStudent: vi.fn(),
  setInProgressDrafts: vi.fn(),
  setPublishedAssessments: vi.fn(),
  setSelectedAssessmentResults: vi.fn(),
  setSelectedTagFilter: vi.fn(),
  setSharedResources: vi.fn(),
  ...overrides,
})

describe('PlannerDashboard mounts all extracted sections (content-asserting)', () => {
  it('renders distinctive content from every planner-dashboard/* component', () => {
    render(<PlannerDashboard {...makeProps()} />)

    // TeacherClassesCard
    expect(screen.getByText('Your Classes')).toBeTruthy()
    expect(screen.getByText('Code: JC1234 | History | 23 students')).toBeTruthy()

    // TagFilterBar
    expect(screen.getByText('Filter by tag:')).toBeTruthy()
    expect(screen.getByText(/All content/)).toBeTruthy()

    // PublishedContentList — both content-type sections
    expect(screen.getByText('Published Assessments')).toBeTruthy()
    expect(screen.getByText('Published Assignments')).toBeTruthy()
    expect(screen.getByText('Quiz 1')).toBeTruthy()
    expect(screen.getByText('HW 2')).toBeTruthy()
    expect(screen.getByText('Active')).toBeTruthy()
    expect(screen.getByText('Closed')).toBeTruthy()

    // SharedResourcesCard
    expect(screen.getByText('Shared Resources')).toBeTruthy()
    expect(screen.getByText('Unit 1 Cards')).toBeTruthy()

    // SubmissionsDetailPanel — header, stats, submissions list
    expect(screen.getByText('Quiz 1 Results')).toBeTruthy()
    expect(screen.getByText('Avg Score')).toBeTruthy()
    expect(screen.getByText('High Score')).toBeTruthy()
    expect(screen.getByText('Ada Lovelace')).toBeTruthy()
    expect(screen.getByText(/Attempt/)).toBeTruthy() // multi-attempt button via contentSubmissionsGroups

    // InProgressDraftsCard
    expect(screen.getByText(/In Progress/)).toBeTruthy()
    expect(screen.getByText('Grace Hopper')).toBeTruthy()
    expect(screen.getByText('End attempt')).toBeTruthy()

    // StandardsSummaryCard
    expect(screen.getByText(/Standards in this Assessment/)).toBeTruthy()
    expect(screen.getByText('CCSS.1')).toBeTruthy()

    // SavedAssessmentsCard
    expect(screen.getByText('Saved Assessments')).toBeTruthy()
    expect(screen.getByText('Saved Quiz')).toBeTruthy()
    expect(screen.getByText('Load')).toBeTruthy()
  })

  it('hides the submissions detail panel when no assessment is selected (guard preserved)', () => {
    render(<PlannerDashboard {...makeProps({ selectedAssessmentResults: null, inProgressDrafts: [] })} />)
    expect(screen.queryByText('Quiz 1 Results')).toBeNull()
    expect(screen.queryByText(/In Progress/)).toBeNull()
    // Sibling sections still render
    expect(screen.getByText('Your Classes')).toBeTruthy()
    expect(screen.getByText('Saved Assessments')).toBeTruthy()
  })
})

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import GradeTab from '../tabs/GradeTab';

// Render-time smoke test for GradeTab. Added with the CQ wave-2 split of
// GradeTab.jsx into tabs/grade/* (mirrors AnalyticsTab.mount.test.jsx from the
// wave-1 analytics split, added for the same reason): build + unit tests pass
// even if a split leaves an unimported component or mis-threaded prop that
// white-screens the tab at runtime. This mounts the real component tree with
// rich props so every extracted section (ErrorBanner, GradingModesPanel,
// ActivityMonitorCard, PeriodFilter, StudentFilter, AssignmentFilter,
// ActiveFiltersSummary, RegradeToggles, IndividualUploadPanel,
// GradingProgress) actually renders content.
vi.mock('../services/api', () => ({
  loadAssignment: vi.fn().mockResolvedValue({
    assignment: { title: 'Lab 1', customMarkers: [], gradingNotes: '', responseSections: [], excludeMarkers: [] },
  }),
  saveAssignmentConfig: vi.fn().mockResolvedValue({}),
  getPeriodStudents: vi.fn().mockResolvedValue({ students: [] }),
  getAuthHeaders: vi.fn().mockResolvedValue({}),
}));

const richProps = () => ({
  status: {
    results: [
      { student_name: 'Alice', assignment: 'Lab 1', filename: 'alice.docx', marker_status: 'unverified', score: 80, letter_grade: 'B' },
      { student_name: 'Bob', assignment: 'Lab 1', filename: 'bob.docx', marker_status: 'verified', score: 95, letter_grade: 'A' },
    ],
    log: ['Started grading', 'Graded alice.docx'],
    is_running: true,
    error: 'Rate limit hit',
    progress: 1,
    total: 2,
    current_file: 'bob.docx',
    session_cost: { total_cost: 0.1234, total_input_tokens: 1000, total_output_tokens: 500, total_api_calls: 3 },
  },
  config: { grade_level: '8', subject: 'science', output_folder: '/tmp', teacher_name: 'T', school_name: 'S' },
  globalAINotes: '',
  savedAssignments: ['Lab 1'],
  savedAssignmentData: { 'Lab 1': { completionOnly: true, dueDate: '2026-06-30T23:59' } },
  setSavedAssignmentData: vi.fn(),
  setStatus: vi.fn(),
  addToast: vi.fn(),
  periods: [{ filename: 'p1.csv', period_name: 'Period 1', row_count: 25 }],
  sortedPeriods: [{ filename: 'p1.csv', period_name: 'Period 1', row_count: 25, students: [{ full: 'Alice Adams' }] }],
  emailApprovals: { 0: 'approved' },
});

describe('GradeTab mounts without crashing (render-time smoke)', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders every extracted grade/* section with rich props', () => {
    render(<GradeTab {...richProps()} />);

    // ErrorBanner (status.error set)
    expect(screen.getByText('Grading Stopped - Error Detected')).toBeTruthy();
    expect(screen.getByText('Rate limit hit')).toBeTruthy();

    // GradingModesPanel header + completion-only count (savedAssignments set)
    expect(screen.getByText('Assignment Grading Modes')).toBeTruthy();
    expect(screen.getByText('(1 completion-only)')).toBeTruthy();

    // ActivityMonitorCard (+ log-entry count badge)
    expect(screen.getByText('Activity Monitor')).toBeTruthy();
    expect(screen.getByText('2 entries')).toBeTruthy();

    // Shell layout header
    expect(screen.getByText('Start Grading')).toBeTruthy();

    // PeriodFilter (periods set)
    expect(screen.getByText('Filter by Class Period')).toBeTruthy();
    expect(screen.getByText('Period 1 (25 students)')).toBeTruthy();

    // StudentFilter (always rendered)
    expect(screen.getByText('Filter by Student')).toBeTruthy();

    // AssignmentFilter (savedAssignments set)
    expect(screen.getByText('Filter by Assignment')).toBeTruthy();
    expect(screen.getByText('Lab 1 (Completion)')).toBeTruthy();

    // RegradeToggles — all three cards (unverified result, results present,
    // approved email approval)
    expect(screen.getByText('Regrade All (Including Verified)')).toBeTruthy();
    expect(screen.getByText('Exclude Already Graded Files')).toBeTruthy();
    expect(screen.getByText('Exclude Already Approved')).toBeTruthy();

    // IndividualUploadPanel
    expect(screen.getByText('Individual Upload')).toBeTruthy();
    expect(screen.getByText('Grade')).toBeTruthy();

    // GradingProgress (is_running true) + session-cost line
    expect(screen.getByText('Progress')).toBeTruthy();
    expect(screen.getByText('1/2')).toBeTruthy();
    expect(screen.getByText('Cost: $0.1234')).toBeTruthy();
    expect(screen.getByText('API Calls: 3')).toBeTruthy();
  });

  it('ActiveFiltersSummary appears once a student filter is typed (state threading through StudentFilter)', () => {
    render(<GradeTab {...richProps()} />);

    // No active-filters banner before any filter is set.
    expect(screen.queryByText('Active Filters:')).toBeNull();

    // Type into the student-filter input (free-text branch — no period selected).
    const input = screen.getByPlaceholderText('Type or select student...');
    fireEvent.change(input, { target: { value: 'Alice Adams' } });

    // StudentFilter confirmation + ActiveFiltersSummary banner both render,
    // proving gradeFilterStudent state threads shell → StudentFilter →
    // ActiveFiltersSummary after the split.
    expect(screen.getByText(/Will only grade files for "Alice Adams"/)).toBeTruthy();
    expect(screen.getByText('Active Filters:')).toBeTruthy();
    expect(screen.getByText('Student: Alice Adams')).toBeTruthy();

    // Clear Filters resets both.
    fireEvent.click(screen.getByText('Clear Filters'));
    expect(screen.queryByText('Active Filters:')).toBeNull();
  });
});

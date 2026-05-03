import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import GradeTab from '../tabs/GradeTab';

// Mock the api module — Grade tab calls api.loadAssignment / api.saveAssignmentConfig
// inline (Codex Round 2 #4: not via prop), so we have to mock the module.
vi.mock('../services/api', () => ({
  loadAssignment: vi.fn().mockResolvedValue({
    assignment: { title: 'Lab 1', importedDoc: null, customMarkers: [], gradingNotes: '', responseSections: [], excludeMarkers: [] },
  }),
  saveAssignmentConfig: vi.fn().mockResolvedValue({}),
}));

const makeProps = (overrides = {}) => ({
  status: { results: [], log: [], is_running: false, error: null, progress: 0, total: 0, current_file: null, session_cost: null },
  config: { ai_model: 'gpt-4o', cost_limit_per_session: 0 },
  savedAssignments: [],
  savedAssignmentData: {},
  setSavedAssignmentData: vi.fn(),
  setStatus: vi.fn(),
  addToast: vi.fn(),
  periods: [],
  selectedPeriod: '',
  setSelectedPeriod: vi.fn(),
  setGradeFilterStudent: vi.fn(),
  loadPeriodStudents: vi.fn(),
  sortedPeriods: [],
  periodStudents: [],
  gradeFilterStudent: '',
  gradeFilterAssignment: '',
  setGradeFilterAssignment: vi.fn(),
  setGradeAssignment: vi.fn(),
  setGradeImportedDoc: vi.fn(),
  availableFiles: [],
  selectedFiles: [],
  setSelectedFiles: vi.fn(),
  emailApprovals: {},
  individualUpload: { file: null, studentName: '', studentInfo: null, showSuggestions: false, isGrading: false, preview: null, result: null },
  setIndividualUpload: vi.fn(),
  getStudentSuggestions: vi.fn(() => []),
  handleIndividualFileSelect: vi.fn(),
  handleIndividualGrade: vi.fn(),
  clearIndividualUpload: vi.fn(),
  MODEL_COST_PER_ASSIGNMENT: {},
  ...overrides,
});

describe('GradeTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('smoke: renders without crashing with minimal props', () => {
    render(<GradeTab {...makeProps()} />);
  });

  it('error-banner dismiss invokes setStatus with an updater that clears error', () => {
    const setStatus = vi.fn();
    render(
      <GradeTab
        {...makeProps({
          status: { ...makeProps().status, error: 'Boom!' },
          setStatus,
        })}
      />,
    );

    fireEvent.click(screen.getByText('Dismiss'));
    expect(setStatus).toHaveBeenCalledTimes(1);
    const updater = setStatus.mock.calls[0][0];
    expect(typeof updater).toBe('function');
    const next = updater({ error: 'Boom!', other: 'keep' });
    expect(next.error).toBeNull();
    expect(next.other).toBe('keep');
  });

  it('activity-log expander toggles internal showActivityLog state', () => {
    // PR 2 moved showActivityLog into GradeTab as local state. ActivityLog
    // returns null when open=false and renders the "Ready to grade..." empty
    // state when open=true with an empty log — that's the observable signal.
    render(<GradeTab {...makeProps()} />);

    expect(screen.queryByText(/Ready to grade/)).toBeNull();

    fireEvent.click(screen.getByText('Activity Monitor').closest('button'));

    expect(screen.getByText(/Ready to grade/)).toBeTruthy();
  });

  it('auto-expand-on-error effect: status.error transition opens the activity log', () => {
    // PR 2 moved the auto-expand effect into GradeTab. When status.error becomes
    // truthy, setShowActivityLog(true) fires — ActivityLog goes from null to
    // visible (the empty-state text becomes present).
    const { rerender } = render(<GradeTab {...makeProps()} />);
    expect(screen.queryByText(/Ready to grade/)).toBeNull();

    rerender(
      <GradeTab
        {...makeProps({ status: { ...makeProps().status, error: 'Something failed' } })}
      />,
    );

    expect(screen.getByText(/Ready to grade/)).toBeTruthy();
  });

  it('assignment-filter selection invokes api.loadAssignment and updates state', async () => {
    const api = await import('../services/api');
    const setGradeAssignment = vi.fn();
    const setGradeFilterAssignment = vi.fn();
    const addToast = vi.fn();

    render(
      <GradeTab
        {...makeProps({
          savedAssignments: ['Lab 1'],
          setGradeAssignment,
          setGradeFilterAssignment,
          addToast,
        })}
      />,
    );

    const select = screen.getByText('Filter by Assignment').parentElement.querySelector('select');
    fireEvent.change(select, { target: { value: 'Lab 1' } });

    expect(setGradeFilterAssignment).toHaveBeenCalledWith('Lab 1');

    // Wait for the async callback to resolve.
    await Promise.resolve();
    await Promise.resolve();

    expect(api.loadAssignment).toHaveBeenCalledWith('Lab 1');
    expect(setGradeAssignment).toHaveBeenCalled();
  });

  it('completion-only toggle on a saved-assignment row mutates savedAssignmentData and persists via api', async () => {
    const api = await import('../services/api');
    const setSavedAssignmentData = vi.fn();
    const addToast = vi.fn();

    render(
      <GradeTab
        {...makeProps({
          savedAssignments: ['Lab 1'],
          savedAssignmentData: { 'Lab 1': { completionOnly: false } },
          setSavedAssignmentData,
          addToast,
        })}
      />,
    );

    // gradingModesExpanded is now local state in GradeTab (PR 2). It defaults
    // to false, so we must click the "Assignment Grading Modes" header first
    // to expand it, then the per-row toggle becomes visible.
    fireEvent.click(screen.getByText('Assignment Grading Modes'));

    // Click the AI Grading / Completion Only toggle button on the Lab 1 row.
    const toggleButton = screen.getByTitle('Click to set as completion only');
    fireEvent.click(toggleButton);

    expect(setSavedAssignmentData).toHaveBeenCalled();
    const updater = setSavedAssignmentData.mock.calls[0][0];
    expect(typeof updater).toBe('function');
    const next = updater({ 'Lab 1': { completionOnly: false } });
    expect(next['Lab 1'].completionOnly).toBe(true);

    // Wait for async work.
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(api.loadAssignment).toHaveBeenCalledWith('Lab 1');
    expect(api.saveAssignmentConfig).toHaveBeenCalled();
  });
});

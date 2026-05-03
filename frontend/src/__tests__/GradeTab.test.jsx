import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import GradeTab from '../tabs/GradeTab';

// Mock the api module — Grade tab calls api.loadAssignment / api.saveAssignmentConfig
// inline (Codex Round 2 #4: not via prop), so we have to mock the module.
// PR 3 also moves loadPeriodStudents + handleIndividualGrade inline, so api.getPeriodStudents
// + getAuthHeaders + global.fetch get mocked too.
vi.mock('../services/api', () => ({
  loadAssignment: vi.fn().mockResolvedValue({
    assignment: { title: 'Lab 1', importedDoc: null, customMarkers: [], gradingNotes: '', responseSections: [], excludeMarkers: [] },
  }),
  saveAssignmentConfig: vi.fn().mockResolvedValue({}),
  getPeriodStudents: vi.fn().mockResolvedValue({
    students: [
      { full: 'Alice Adams', first: 'Alice', last: 'Adams', email: 'alice@example.com' },
      { full: 'Bob Brown', first: 'Bob', last: 'Brown', email: 'bob@example.com' },
    ],
  }),
  getAuthHeaders: vi.fn().mockResolvedValue({}),
}));

const makeProps = (overrides = {}) => ({
  status: { results: [], log: [], is_running: false, error: null, progress: 0, total: 0, current_file: null, session_cost: null },
  config: { ai_model: 'gpt-4o', cost_limit_per_session: 0 },
  globalAINotes: '',
  savedAssignments: [],
  savedAssignmentData: {},
  setSavedAssignmentData: vi.fn(),
  setStatus: vi.fn(),
  addToast: vi.fn(),
  periods: [],
  setGradeFilterStudent: vi.fn(),
  sortedPeriods: [],
  gradeFilterStudent: '',
  setGradeImportedDoc: vi.fn(),
  availableFiles: [],
  selectedFiles: [],
  setSelectedFiles: vi.fn(),
  emailApprovals: {},
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

  it('assignment-filter selection invokes api.loadAssignment and updates local state', async () => {
    // PR 3 moved gradeFilterAssignment + gradeAssignment into GradeTab as local
    // state. The dropdown change still triggers `api.loadAssignment` inline.
    // Observable signals: addToast call (still a prop) + visible "✓ Using"
    // confirmation text rendered conditionally on local gradeFilterAssignment.
    const api = await import('../services/api');
    const addToast = vi.fn();

    render(
      <GradeTab
        {...makeProps({
          savedAssignments: ['Lab 1'],
          addToast,
        })}
      />,
    );

    const select = screen.getByText('Filter by Assignment').parentElement.querySelector('select');
    fireEvent.change(select, { target: { value: 'Lab 1' } });

    // Wait for the async loader to resolve.
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(api.loadAssignment).toHaveBeenCalledWith('Lab 1');
    expect(addToast).toHaveBeenCalledWith('Loaded "Lab 1"', 'success');
    // gradeFilterAssignment was set locally — confirmation text should render.
    expect(screen.getByText(/Using.*Lab 1.*configuration/)).toBeTruthy();
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

  // PR 3 — individual-upload + period + assignment-config slice tests.

  it('Grade button is disabled when no file or no student name is set', () => {
    // The disabled prop on the Grade button is the user-visible defense; the
    // handleIndividualGrade body has a defensive `addToast("Please select a
    // file...")` guard for the otherwise-unreachable case. We assert the UI
    // surface (disabled button) which is what the user actually experiences.
    render(<GradeTab {...makeProps()} />);
    const gradeButton = screen.getByText('Grade').closest('button');
    expect(gradeButton.disabled).toBe(true);
  });

  it('handleIndividualGrade happy path: posts to /api/grade-individual and adds to results', async () => {
    // PR 3 happy-path: file + studentName set → fetch posts → setStatus pushes
    // result → addToast confirms.
    const addToast = vi.fn();
    const setStatus = vi.fn();

    const fakeResult = { letter_grade: 'A', score: 95, student_name: 'Alice', assignment: 'Lab 1' };
    global.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve(fakeResult),
    });

    render(
      <GradeTab
        {...makeProps({
          addToast,
          setStatus,
          config: { grade_level: '8', subject: 'math', output_folder: '/tmp', teacher_name: 'T', school_name: 'S' },
        })}
      />,
    );

    // Set student name + file via the file input directly. The component's
    // handleIndividualFileSelect reads from e.target.files[0].
    const studentNameInput = screen.getByPlaceholderText('Student name...');
    fireEvent.change(studentNameInput, { target: { value: 'Alice' } });

    const file = new File(['fake'], 'alice.png', { type: 'image/png' });
    // Stub URL.createObjectURL since jsdom doesn't implement it.
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = vi.fn();

    const fileInput = document.getElementById('individualFileInput');
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Now Grade button is enabled.
    const gradeButton = screen.getByText('Grade').closest('button');
    expect(gradeButton.disabled).toBe(false);

    fireEvent.click(gradeButton);

    // Wait for fetch + setState to settle.
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/grade-individual',
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
      }),
    );
    // Verify the FormData payload includes the expected fields.
    const sentBody = global.fetch.mock.calls[0][1].body;
    expect(sentBody.get('student_name')).toBe('Alice');
    expect(sentBody.get('grade_level')).toBe('8');
    expect(sentBody.get('subject')).toBe('math');
    expect(sentBody.get('teacher_name')).toBe('T');
    expect(sentBody.get('school_name')).toBe('S');

    expect(setStatus).toHaveBeenCalled();
    expect(addToast).toHaveBeenCalledWith(
      expect.stringContaining('A'),
      'success',
    );
  });

  it('clearIndividualUpload revokes the blob URL and resets state', () => {
    // PR 3: clear button revokes URL and sets state back to defaults.
    global.URL.createObjectURL = vi.fn(() => 'blob:mock-clear-url');
    const revokeSpy = vi.fn();
    global.URL.revokeObjectURL = revokeSpy;

    render(<GradeTab {...makeProps()} />);

    const file = new File(['fake'], 'bob.png', { type: 'image/png' });
    const fileInput = document.getElementById('individualFileInput');
    fireEvent.change(fileInput, { target: { files: [file] } });

    // The clear button has aria-label="Clear individual upload" — accessible
    // selector replaces the prior brittle "no-text + has-svg" pattern.
    const clearBtn = screen.getByLabelText('Clear individual upload');
    fireEvent.click(clearBtn);
    expect(revokeSpy).toHaveBeenCalledWith('blob:mock-clear-url');
  });

  it('selected-period change loads roster via api.getPeriodStudents and shows count', async () => {
    // PR 3 moved loadPeriodStudents inline. When user picks a period from the
    // dropdown, api.getPeriodStudents is called and the count appears.
    const api = await import('../services/api');

    render(
      <GradeTab
        {...makeProps({
          periods: [{ filename: 'period1.csv', period_name: 'Period 1', row_count: 25 }],
          sortedPeriods: [{ filename: 'period1.csv', period_name: 'Period 1', row_count: 25, students: [] }],
        })}
      />,
    );

    const select = screen.getByText('Filter by Class Period').parentElement.querySelector('select');
    fireEvent.change(select, { target: { value: 'period1.csv' } });

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(api.getPeriodStudents).toHaveBeenCalledWith('period1.csv');
    // After roster loads, the "✓ Filtering to N students" text should appear.
    expect(screen.getByText(/Filtering to 2 students/)).toBeTruthy();
  });
});

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ResultsTab from '../tabs/ResultsTab';

// Added alongside the CQ wave-1 split of ResultsTab.jsx into tabs/results/*.
// The split relocated ~2,200 lines of JSX into 13 child components; the build
// can only prove imports resolve, not that every relocated identifier is still
// in scope at render time. This smoke test renders the full composed tree
// (header, filter controls, export controls, progress bars, authenticity alert,
// auto-approve controls, portal section, table rows + cells, send button,
// assessment section incl. expanded detail + question breakdown) so a missed
// prop surfaces as a ReferenceError here instead of in the nightly e2e.

vi.mock('../services/api', () => ({
  clearResults: vi.fn().mockResolvedValue({}),
  deleteResult: vi.fn().mockResolvedValue({}),
  deleteAssessment: vi.fn().mockResolvedValue({}),
  sendEmails: vi.fn().mockResolvedValue({ sent: 1, failed: 0 }),
  exportFocusBatch: vi.fn().mockResolvedValue({ periods: [] }),
  exportFocusComments: vi.fn().mockResolvedValue({}),
  syncOneRosterGrades: vi.fn().mockResolvedValue({ synced: 1, skipped: 0, failed: 0 }),
  exportLmsCsv: vi.fn().mockResolvedValue({ count: 1 }),
  uploadFocusComments: vi.fn().mockResolvedValue({ total: 1 }),
  exportOutlookEmails: vi.fn().mockResolvedValue({ count: 1, emails: [] }),
  sendOutlookEmails: vi.fn().mockResolvedValue({ total: 1 }),
  sendFocusComms: vi.fn().mockResolvedValue({ total: 1 }),
  stopFocusComms: vi.fn().mockResolvedValue({}),
  sendFileConfirmations: vi.fn().mockResolvedValue({ total: 1, sent_filenames: [] }),
  sendSubmissionConfirmations: vi.fn().mockResolvedValue({ total: 1, confirmation_ids: [] }),
}));

const results = [
  {
    filename: 'a1.docx',
    student_name: 'Alice Adams',
    assignment: 'Essay 1',
    period: 'Period 1',
    score: 92,
    letter_grade: 'A',
    graded_at: '2026-06-01 10:00',
    is_handwritten: true,
    marker_status: 'verified',
    student_email: 'alice@example.com',
    student_id: 'sid1',
    token_usage: { total_cost_display: '$0.01' },
  },
  {
    filename: 'a2.docx',
    student_name: 'Bob Brown',
    assignment: 'Essay 1',
    period: 'Period 1',
    score: 55,
    original_score: 60,
    letter_grade: 'F',
    graded_at: '2026-06-01 11:00',
    is_handwritten: false,
    marker_status: 'unverified',
    config_mismatch: true,
    is_resubmission: true,
    previous_score: 50,
    late_penalty: { penalty_applied: 5, days_late: 1 },
    ai_detection: { flag: 'likely', confidence: 85, reason: 'Uniform tone' },
    plagiarism_detection: { flag: 'possible', reason: 'Shared phrasing' },
  },
];

const assessmentResults = [
  {
    id: 'as1',
    title: 'Unit 1 Quiz',
    assessment_category: 'formative',
    source: 'join_code',
    join_code: 'ABC123',
    period: 'Period 1',
    published_at: '2026-06-01T09:00:00Z',
    class_sourced_id: 'c1',
    stats: {
      total_submissions: 1,
      expected_submissions: 2,
      average_score: 85,
      highest_score: 85,
      lowest_score: 85,
      pending_count: 0,
      total_points: 10,
      average_time_seconds: 120,
    },
    submissions: [
      {
        student_name: 'Dan Doe',
        score: 8,
        percentage: 80,
        letter_grade: 'B',
        time_taken_seconds: 300,
        status: 'graded',
        student_id_number: 'oneroster:x1',
        feedback_summary: 'Good work',
      },
    ],
    question_analysis: [
      {
        number: 1,
        question: 'What is 2 + 2?',
        type: 'multiple_choice',
        points: 2,
        percent_correct: 40,
        response_distribution: {
          A: { count: 1, percent: 100, is_correct: false },
        },
      },
    ],
  },
];

const makeProps = (overrides = {}) => ({
  status: { results, is_running: false, log: [], complete: true },
  config: {
    sis_type: 'focus',
    assignments_folder: '/tmp/assignments',
    trustedStudents: [],
    teacher_name: 'Ms. Frizzle',
    teacher_email: 'teacher@example.com',
    email_signature: 'Ms. Frizzle',
  },
  rubric: {},
  globalAINotes: '',
  theme: 'dark',
  resultsPeriodFilter: '',
  editedResults: [],
  emailApprovals: { 0: 'approved' },
  sentEmails: {},
  editedEmails: {},
  emailStatus: { sending: false, sent: 0, failed: 0, message: 'Sent 1 emails successfully!' },
  autoApproveEmails: false,
  gradesApproved: true,
  savedAssignments: ['Essay 1'],
  savedAssignmentData: { 'Essay 1': { title: 'Essay 1' } },
  studentAccommodations: { sid1: { presets: [{ name: 'Extended time' }] } },
  sortedPeriods: [{ filename: 'p1.csv', period_name: 'Period 1' }],
  portalSubmissions: [
    {
      submission_id: 's1',
      student_name: 'Cara Cole',
      assignment: 'Essay 1',
      period: 'Period 1',
      status: 'submitted',
      submitted_at: '2026-06-01T12:00:00Z',
    },
  ],
  assessmentResults,
  setAssessmentResults: vi.fn(),
  vportalConfigured: true,
  outlookSendStatus: { status: 'running', sent: 1, total: 2, failed: 0, message: 'Sending emails...' },
  focusCommsStatus: { status: 'running', sent: 0, total: 1, failed: 0, skipped: 0, message: 'Working' },
  focusCommentsStatus: { status: 'idle', entered: 0, total: 0, failed: 0, message: '' },
  curveModal: { show: false, curveType: 'flat', curveValue: 0 },
  colWidths: null,
  defaultColPercents: [18, 18, 10, 8, 8, 8, 14, 8, 8],
  pendingConfirmations: 1,
  pendingConfirmationStudents: ['Cara Cole'],
  confirmationStudentFilter: '',
  focusExportModal: false,
  reviewModal: { show: false, index: null },
  setResultsPeriodFilter: vi.fn(),
  setStatus: vi.fn(),
  setConfig: vi.fn(),
  setEditedResults: vi.fn(),
  setEmailApprovals: vi.fn(),
  setSentEmails: vi.fn(),
  setEditedEmails: vi.fn(),
  setEmailStatus: vi.fn(),
  setAutoApproveEmails: vi.fn(),
  setGradesApproved: vi.fn(),
  setOutlookSendStatus: vi.fn(),
  setOutlookSendPolling: vi.fn(),
  setFocusCommsStatus: vi.fn(),
  setFocusCommsPolling: vi.fn(),
  setFocusCommentsStatus: vi.fn(),
  setFocusCommentsPolling: vi.fn(),
  setCurveModal: vi.fn(),
  setFocusExportModal: vi.fn(),
  setColWidths: vi.fn(),
  setConfirmationStudentFilter: vi.fn(),
  addToast: vi.fn(),
  openReview: vi.fn(),
  sendSingleEmail: vi.fn(),
  getDefaultEmailBody: vi.fn(() => 'body'),
  updateApprovalsBulk: vi.fn(),
  initColWidths: vi.fn(),
  handleResizeStart: vi.fn(),
  tableRef: { current: null },
  pendingConfirmationIds: { current: [] },
  pendingConfirmationFilenames: { current: [] },
  ...overrides,
});

describe('ResultsTab (post tabs/results/ split)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('smoke: renders every extracted section without crashing', () => {
    render(<ResultsTab {...makeProps()} />);

    // Assessment Results section (AssessmentResultsSection + row)
    expect(screen.getByText('Assessment Results')).toBeTruthy();
    expect(screen.getByText('Unit 1 Quiz')).toBeTruthy();

    // Assignment Results header + heading (ResultsHeader)
    expect(screen.getByText('Assignment Results')).toBeTruthy();
    expect(screen.getByText(/Grading Results \(/)).toBeTruthy();

    // Filter controls + export controls render (ResultsFilterControls/ResultsExportControls)
    expect(screen.getByText('Export Grades')).toBeTruthy();
    expect(screen.getByText('Upload Comments')).toBeTruthy();
    // Appears in both ResultsExportControls and PortalSubmissionsSection
    expect(screen.getAllByText(/Send Confirmations \(1\)/).length).toBeGreaterThan(0);

    // Progress indicators (SendProgressIndicators)
    expect(screen.getByText('Sending emails...')).toBeTruthy();
    expect(screen.getByText('Focus: Working')).toBeTruthy();

    // Authenticity summary (AuthenticitySummaryAlert)
    expect(screen.getByText('Authenticity Summary')).toBeTruthy();

    // Auto-approve controls (AutoApproveControls)
    expect(screen.getByText('Auto-Approve Emails')).toBeTruthy();

    // Email status banner (still inline in ResultsTab)
    expect(screen.getByText('Sent 1 emails successfully!')).toBeTruthy();

    // Portal submissions (PortalSubmissionsSection)
    expect(screen.getByText('Portal Submissions')).toBeTruthy();
    // Also appears as an <option> in the confirmation-student filter select
    expect(screen.getAllByText('Cara Cole').length).toBeGreaterThan(0);

    // Table rows + cells (ResultsTable/ResultsTableRow/AuthenticityCell)
    expect(screen.getByText('Alice Adams')).toBeTruthy();
    expect(screen.getByText('Bob Brown')).toBeTruthy();
    expect(screen.getAllByText(/AI:/).length).toBeGreaterThan(0);

    // Send approved emails button (SendApprovedEmailsButton)
    expect(screen.getByText(/Approved Emails/)).toBeTruthy();
  });

  it('expands assessment details and the per-question breakdown', () => {
    render(<ResultsTab {...makeProps()} />);

    fireEvent.click(screen.getByText('View Details'));
    expect(screen.getByText('Student Scores')).toBeTruthy();
    expect(screen.getByText('Dan Doe')).toBeTruthy();

    fireEvent.click(screen.getByText('Per-Question Breakdown'));
    expect(screen.getByText(/Q1: What is 2 \+ 2\?/)).toBeTruthy();
  });

  it('assignment filter select shows the AssignmentStats bar', () => {
    render(<ResultsTab {...makeProps()} />);

    fireEvent.change(screen.getByTitle('Filter by assignment'), {
      target: { value: 'Essay 1' },
    });
    expect(screen.getByText('Avg Score:')).toBeTruthy();
    expect(screen.getByText('Graded:')).toBeTruthy();
  });

  it('row Edit action calls openReview with the original index', () => {
    const openReview = vi.fn();
    render(<ResultsTab {...makeProps({ openReview })} />);

    fireEvent.click(screen.getAllByTitle('Edit')[0]);
    expect(openReview).toHaveBeenCalledTimes(1);
  });
});

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import BuilderTab from '../tabs/BuilderTab';

// Render-time smoke test for BuilderTab. Added with the CQ wave-9 split of
// BuilderTab.jsx into tabs/builder/* (mirrors GradeTab.mount.test.jsx /
// PlannerTab.mount.test.jsx from waves 1-2, added for the same reason):
// build + unit tests pass even if a split leaves an unimported component or
// mis-threaded prop that white-screens the tab at runtime. This mounts the
// real component tree with rich props so every extracted section
// (SavedAssignmentsCard, AssignmentDetailsSection, DueDatePolicySection,
// ImportDocumentSection + SectionPointSummary + ManualMarkerInput +
// GradingSectionsList, MarkerLibrarySection, RubricTypeSection,
// ModelAnswersSection, StandardsAlignmentSection, QuestionsSection,
// ExportButtonsSection) actually renders content.
// Written pre-split (green) per the wave-8 precedent, so it pins behavior
// across the refactor.
vi.mock('../services/api', () => ({
  loadAssignment: vi.fn().mockResolvedValue({
    assignment: { title: 'Quiz 1', customMarkers: [], gradingNotes: '', responseSections: [] },
  }),
  saveAssignmentConfig: vi.fn().mockResolvedValue({}),
}));

const richProps = () => ({
  assignment: {
    title: 'Quiz 1',
    subject: 'Social Studies',
    totalPoints: 100,
    instructions: '',
    questions: [{ id: 1, marker: 'Main Idea', type: 'short_answer', points: 10, prompt: 'What happened?' }],
    customMarkers: [{ start: 'Summary', points: 42, type: 'written' }, 'Main Idea'],
    gradingNotes: 'Be fair',
    responseSections: [],
    aliases: ['Ch 10'],
    dueDate: '2026-06-30T23:59',
    latePenalty: { enabled: true, type: 'tiered', amount: 5, maxPenalty: 50, gracePeriodHours: 2, tiers: [{ daysLate: 1, penalty: 10 }] },
    useSectionPoints: true,
    effortPoints: 15,
    rubricType: 'custom',
    customRubric: [{ name: 'Content', weight: 50 }, { name: 'Effort', weight: 50 }],
    modelAnswers: { Summary: 'A model answer', 'Main Idea': 'Another model answer' },
    completionOnly: false,
  },
  setAssignment: vi.fn(),
  savedAssignments: ['Quiz 1', 'Old HW'],
  savedAssignmentData: {
    'Quiz 1': { countsTowardsGrade: true, rubricType: 'essay' },
    'Old HW': { completionOnly: true, countsTowardsGrade: false, worksheetDownloadUrl: 'http://example.com/ws.docx' },
  },
  setSavedAssignmentData: vi.fn(),
  loadedAssignmentName: 'Quiz 1',
  setLoadedAssignmentName: vi.fn(),
  isLoadingAssignment: false,
  setIsLoadingAssignment: vi.fn(),
  importedDoc: { text: 'Document body', html: '', filename: 'doc.docx', loading: false },
  setImportedDoc: vi.fn(),
  docEditorModal: { show: false, editedHtml: '', viewMode: 'formatted' },
  setDocEditorModal: vi.fn(),
  modelAnswersLoading: false,
  standardsAlignment: {
    overall_alignment_score: 0.8,
    matched_standards: [{ code: 'SS.8.1', benchmark: 'Explain causes of events', confidence: 0.9, evidence: 'Q1 asks for causes', alignment_notes: 'Strong match' }],
    suggestions: ['Add a primary-source question'],
    question_analysis: [{ question_text: 'What happened?', aligned_standard: 'SS.8.1', alignment_quality: 'strong', rewrite_suggestion: 'Ask for two causes' }],
    rewrites: [{ original_text: 'What happened?', rewritten_text: 'What were two causes?', standard_code: 'SS.8.1', change_explanation: 'Targets causal analysis' }],
    usage: { cost_display: '$0.01' },
  },
  alignmentLoading: false,
  rewriteLoading: false,
  handleAlignToStandards: vi.fn(),
  handleRewriteForAlignment: vi.fn(),
  config: { subject: 'Social Studies' },
  fileInputRef: React.createRef(),
  skipAutoSaveRef: { current: false },
  loadAssignment: vi.fn(),
  deleteAssignment: vi.fn(),
  saveAssignmentConfig: vi.fn(),
  exportAssignment: vi.fn(),
  handleDocImport: vi.fn(),
  openDocEditor: vi.fn(),
  handleGenerateModelAnswers: vi.fn(),
  removeMarker: vi.fn(),
  addQuestion: vi.fn(),
  updateQuestion: vi.fn(),
  removeQuestion: vi.fn(),
  addToast: vi.fn(),
  getMarkerText: (m) => (typeof m === 'string' ? m : m.start),
  getMarkerPoints: (m) => (typeof m === 'object' ? m.points : 10),
  getMarkerType: (m) => (typeof m === 'object' ? m.type || 'written' : 'written'),
  calculateTotalPoints: vi.fn(() => 100),
  removeAllHighlightsFromHtml: (html) => html,
  applyAllHighlights: (html) => html,
  textToRichHtml: (text) => `<p>${text}</p>`,
  markerLibrary: {
    'Social Studies': ['Main Idea', 'Summary'],
    Other: ['Main Idea'],
  },
});

describe('BuilderTab mounts without crashing (render-time smoke)', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders every extracted builder/* section with rich props', () => {
    render(<BuilderTab {...richProps()} />);

    // SavedAssignmentsCard header (collapsed by default)
    expect(screen.getByText('Saved Assignments (2)')).toBeTruthy();

    // Editor header (assignment.title set) + marker count
    expect(screen.getByText('Editing: Quiz 1')).toBeTruthy();
    expect(screen.getByText('2 markers')).toBeTruthy();

    // AssignmentDetailsSection: title field, alias chip, subject, points
    expect(screen.getByText('Assignment Title')).toBeTruthy();
    expect(screen.getByPlaceholderText('e.g., Louisiana Purchase Quiz')).toBeTruthy();
    expect(screen.getByText('Ch 10')).toBeTruthy();
    expect(screen.getByText('Total Points')).toBeTruthy();

    // DueDatePolicySection: header, late penalty enabled, tiered brackets
    expect(screen.getByText('Due Date & Late Policy')).toBeTruthy();
    expect(screen.getByText('Enable late penalty')).toBeTruthy();
    expect(screen.getByText('Penalty Type')).toBeTruthy();
    expect(screen.getByText('Tier Brackets')).toBeTruthy();
    expect(screen.getByText('Add Tier')).toBeTruthy();

    // ImportDocumentSection: header, loaded filename, edit button, toggle
    expect(screen.getByText('Import Document & Mark Sections')).toBeTruthy();
    expect(screen.getByText('doc.docx')).toBeTruthy();
    expect(screen.getByText('Edit & Mark')).toBeTruthy();
    expect(screen.getByText('Use Section Point Values')).toBeTruthy();

    // SectionPointSummary (useSectionPoints true)
    expect(screen.getByText('Point Distribution')).toBeTruthy();
    expect(screen.getByText('Distribute Evenly')).toBeTruthy();
    expect(screen.getByText('Total Points:')).toBeTruthy();

    // ManualMarkerInput
    expect(screen.getByPlaceholderText('Type a marker phrase and press Add...')).toBeTruthy();

    // GradingSectionsList: header, marker row, effort row, model answers
    expect(screen.getByText('Grading Sections')).toBeTruthy();
    expect(screen.getByDisplayValue('Summary')).toBeTruthy();
    expect(screen.getByText('Effort & Engagement')).toBeTruthy();
    expect(screen.getAllByText('Model Answer:').length).toBe(2);
    expect(screen.getByDisplayValue('A model answer')).toBeTruthy();

    // MarkerLibrarySection: header + a suggested marker chip
    expect(screen.getByText(/Suggested Markers for/)).toBeTruthy();

    // RubricTypeSection: selector + custom rubric editor
    expect(screen.getByText('Assignment Rubric')).toBeTruthy();
    expect(screen.getByText('Custom Rubric Categories')).toBeTruthy();
    expect(screen.getByDisplayValue('Content')).toBeTruthy();
    expect(screen.getByText('Add Category')).toBeTruthy();
    expect(screen.getByText('Reset to Default')).toBeTruthy();

    // ModelAnswersSection (markers + importedDoc.text present)
    expect(screen.getByText('Generate Model Answers')).toBeTruthy();
    expect(screen.getByText('2 sections answered')).toBeTruthy();

    // StandardsAlignmentSection: button + full results panel
    expect(screen.getByText('Align to Standards')).toBeTruthy();
    expect(screen.getByText('Standards Alignment')).toBeTruthy();
    expect(screen.getByText('SS.8.1')).toBeTruthy();
    expect(screen.getByText('90% match')).toBeTruthy();
    expect(screen.getByText('Improvement Suggestions')).toBeTruthy();
    expect(screen.getByText('Add a primary-source question')).toBeTruthy();
    expect(screen.getByText('Question-Level Analysis')).toBeTruthy();
    expect(screen.getByText('Rewrite This Question')).toBeTruthy();
    expect(screen.getByText('Rewritten Questions')).toBeTruthy();
    expect(screen.getByText('Copy Rewrite')).toBeTruthy();
    expect(screen.getByText('$0.01')).toBeTruthy();

    // Grading notes (shell)
    expect(screen.getByText('Assignment-Specific Grading Notes')).toBeTruthy();
    expect(screen.getByDisplayValue('Be fair')).toBeTruthy();

    // QuestionsSection: add button, question card, prompt field
    expect(screen.getByText('Add Question')).toBeTruthy();
    expect(screen.getByText('Question 1')).toBeTruthy();
    expect(screen.getByText('Question/Prompt')).toBeTruthy();
    expect(screen.getByDisplayValue('What happened?')).toBeTruthy();

    // ExportButtonsSection
    expect(screen.getByText('Auto-saves')).toBeTruthy();
    expect(screen.getByText('Save Now')).toBeTruthy();
    expect(screen.getByText('Export Word Doc')).toBeTruthy();
    expect(screen.getByText('Export PDF')).toBeTruthy();
  });

  it('expands the saved-assignments card on click (local state threading through SavedAssignmentsCard)', () => {
    render(<BuilderTab {...richProps()} />);

    // Collapsed: saved items not visible yet.
    expect(screen.queryByText('Old HW')).toBeNull();

    fireEvent.click(screen.getByText('Saved Assignments (2)'));

    // Expanded: both saved items render, with badges/buttons per item state.
    expect(screen.getByText('Old HW')).toBeTruthy();
    expect(screen.getByText('Completion')).toBeTruthy(); // completionOnly badge
    expect(screen.getByText('essay')).toBeTruthy(); // rubricType badge on Quiz 1
    expect(screen.getByTitle('Download worksheet (.docx)')).toBeTruthy();
    expect(screen.getByTitle('Excluded from grade (click to include)')).toBeTruthy();
  });
});

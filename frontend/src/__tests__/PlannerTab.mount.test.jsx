import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import PlannerTab from '../tabs/PlannerTab';

// Render-time smoke test for PlannerTab. Added with the CQ wave-3 split of
// PlannerTab.jsx into tabs/planner/* (mirrors GradeTab.mount.test.jsx from
// the wave-2 grade split, added for the same reason): build + unit tests pass
// even if a split leaves an unimported component or mis-threaded prop that
// white-screens the tab at runtime. This mounts the real component tree in
// every planner sub-mode with rich props so each extracted piece
// (PlannerModeToggle, PlannerLessonMode, PlannerAssessmentMode,
// PlannerDashboardMode, PlannerModals, useTagRow's renderTagRow,
// useLessonGeneration / usePlannerDocs / usePublishAssessment /
// useShareWithClasses) actually renders content.
vi.mock('../services/api', () => ({
  loadAssignment: vi.fn().mockResolvedValue({ assignment: {} }),
  getStandards: vi.fn().mockResolvedValue({ standards: [] }),
  generateLessonPlan: vi.fn().mockResolvedValue({ lessonPlan: {} }),
  brainstormLessonIdeas: vi.fn().mockResolvedValue({ ideas: [] }),
  alignDocumentToStandards: vi.fn().mockResolvedValue({}),
  extractTextFromFile: vi.fn().mockResolvedValue({ text: '' }),
  listClasses: vi.fn().mockResolvedValue({ classes: [] }),
  getPeriodStudents: vi.fn().mockResolvedValue({ students: [] }),
  saveLessonPlan: vi.fn().mockResolvedValue({}),
  setContentTags: vi.fn().mockResolvedValue({ success: true }),
  updateSharedResourceUnit: vi.fn().mockResolvedValue({ success: true }),
  publishToClass: vi.fn().mockResolvedValue({ success: true }),
  publishAssessmentToPortal: vi.fn().mockResolvedValue({ success: true }),
  getAuthHeaders: vi.fn().mockResolvedValue({}),
  listAssignments: vi.fn().mockResolvedValue({ assignments: [], assignmentData: {} }),
}));

const baseProps = () => ({
  status: { results: [], log: [], is_running: false, error: null },
  config: { ai_model: 'gpt-4o', subject: 'Math', grade_level: '8', state: 'FL' },
  user: null,
  activeTab: 'planner',
  plannerMode: 'lesson',
  addToast: vi.fn(),
  unitConfig: {
    title: '', duration: 1, periodLength: 50, type: 'Assignment',
    format: 'Word', requirements: '', totalQuestions: 10, questionsPerSection: 0,
  },
  selectedStandards: [],
  standards: [{ code: 'MA.8.NSO.1.1', benchmark: 'Number sense and operations' }],
  uploadedDocs: [{ filename: 'notes.pdf', size: 2048 }],
  supportDocs: [],
  savedAssignments: [],
  teacherClasses: [],
  periods: [],
  savedAssignmentData: {},
  contentOnly: false,
  assessmentTemplates: [],
  assessmentConfig: {
    title: '', duration: 1, requirements: '', totalQuestions: 10,
    questionTypes: {}, format: 'Word',
    dokDistribution: { 1: 0, 2: 0, 3: 0, 4: 0 }, sources: [],
  },
  lessonPlan: null,
  generatedAssignment: null,
  generatedAssessment: null,
  assignment: null,
  assessmentAnswers: {},
  selectedSources: [],
  selectedAssessmentResults: null,
  publishedAssessments: [],
  loadingPublished: false,
  inProgressDrafts: [],
  loadingResults: false,
  sharedResources: [],
  loadingSharedResources: false,
  contentSubmissionsGroups: [],
  savedAssessments: [],
  loadingSavedAssessments: false,
  savedLessons: { units: {} },
  allTeacherTags: [],
  selectedTagFilter: '',
  assessmentLoading: false,
  gradingAssessment: false,
  savingAssessment: false,
  saveAssessmentName: '',
  studentAccommodations: {},
  domainNameMap: {},
  getDomains: () => [],
  getTotalQuestionCount: () => 0,
  itemMatchesTagFilter: () => true,
  getSubjectSectionDefaults: () => ({
    multiple_choice: true, short_answer: true, math_computation: true,
    geometry_visual: true, graphing: true, data_analysis: true,
    extended_writing: false, vocabulary: false, true_false: false,
  }),
  standardsScrollRef: { current: null },
  assessmentStandardsScrollRef: { current: null },
  // Setters/handlers invoked asynchronously (effects, promise callbacks) need
  // real stubs: the Proxy get-trap fallback below does NOT survive the JSX
  // spread in render(<PlannerTab {...makeProps()} />) — spreading copies own
  // keys only, so only listed props reach the component.
  setStandards: vi.fn(),
  setLessonPlan: vi.fn(),
  setSelectedStandards: vi.fn(),
  setUploadedDocs: vi.fn(),
  setTeacherClasses: vi.fn(),
  setSupportDocs: vi.fn(),
  setSharedResources: vi.fn(),
  setPublishedAssessments: vi.fn(),
  fetchTeacherClasses: vi.fn(),
  fetchSavedLessons: vi.fn(),
});

// Missing handlers/setters auto-stub as vi.fn() via Proxy (PlannerTab.test
// precedent) — props the tree dereferences by shape must live in baseProps.
const makeProps = (overrides = {}) => {
  const base = { ...baseProps(), ...overrides };
  return new Proxy(base, {
    get(target, prop) {
      if (prop in target) return target[prop];
      if (typeof prop === 'symbol') return undefined;
      return vi.fn();
    },
    has(target, prop) {
      return prop in target;
    },
  });
};

describe('PlannerTab mounts without crashing (render-time smoke)', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('lesson mode: mode toggle + PlannerLessonMode render real content', () => {
    render(<PlannerTab {...makeProps()} />);

    // PlannerModeToggle — all five sub-mode buttons
    expect(screen.getByText('Lesson Planning')).toBeTruthy();
    expect(screen.getByText('Assessment Generator')).toBeTruthy();
    expect(screen.getByText('Student Portal')).toBeTruthy();
    expect(screen.getByText('Calendar')).toBeTruthy();
    expect(screen.getByText('Tools')).toBeTruthy();

    // PlannerLessonMode → PlannerLesson sidebar content (standards +
    // uploaded reference docs threaded through {...props}; docUploading /
    // matchResults threaded from usePlannerDocs)
    expect(screen.getByText(/Select Standards/)).toBeTruthy();
    expect(screen.getByText(/Reference Documents/)).toBeTruthy();
    expect(screen.getByText('notes.pdf')).toBeTruthy();
    expect(screen.getByText(/Brainstorm Assignment Ideas/)).toBeTruthy();
  });

  it('mode toggle wiring: Student Portal click flips mode + fires dashboard fetches', () => {
    const setPlannerMode = vi.fn();
    const fetchPublishedAssessments = vi.fn();
    const fetchSharedResources = vi.fn();
    const fetchTeacherTags = vi.fn();
    const fetchSavedAssessments = vi.fn();
    render(<PlannerTab {...makeProps({
      setPlannerMode, fetchPublishedAssessments, fetchSharedResources,
      fetchTeacherTags, fetchSavedAssessments,
    })} />);

    fireEvent.click(screen.getByText('Student Portal').closest('button'));
    expect(setPlannerMode).toHaveBeenCalledWith('dashboard');
    expect(fetchPublishedAssessments).toHaveBeenCalled();
    expect(fetchSharedResources).toHaveBeenCalled();
    expect(fetchTeacherTags).toHaveBeenCalled();
    expect(fetchSavedAssessments).toHaveBeenCalled();
  });

  it('assessment mode: PlannerAssessmentMode renders the generated assessment preview', () => {
    render(<PlannerTab {...makeProps({
      plannerMode: 'assessment',
      generatedAssessment: {
        title: 'Unit 1 Checkpoint',
        total_points: 30,
        time_limit: 45,
        instructions: 'Answer every question.',
        dok_summary: { dok_1_count: 1, dok_2_count: 2, dok_3_count: 1, dok_4_count: 0 },
        sections: [],
      },
    })} />);

    expect(screen.getByText('Unit 1 Checkpoint')).toBeTruthy();
    expect(screen.getByText('Answer every question.')).toBeTruthy();
  });

  it('dashboard mode: PlannerDashboardMode renders items through the real useTagRow renderTagRow', () => {
    render(<PlannerTab {...makeProps({
      plannerMode: 'dashboard',
      publishedAssessments: [
        { id: 'pa1', join_code: 'ABC123', title: 'Quiz 1', active: true, submission_count: 0 },
      ],
    })} />);

    expect(screen.getByText('Quiz 1')).toBeTruthy();
    // renderTagRow output for an item with no unit/tags — proves the
    // useTagRow hook threads shell → PlannerDashboardMode → PlannerDashboard.
    expect(screen.getByText('No unit')).toBeTruthy();
    expect(screen.getByText('+ Tag')).toBeTruthy();
  });

  it('tools mode: PlannerTools renders (shareWithClass threaded from useShareWithClasses)', () => {
    render(<PlannerTab {...makeProps({ plannerMode: 'tools' })} />);
    expect(screen.getByText(/Generate Study Guide/)).toBeTruthy();
  });

  it('calendar mode: PlannerCalendar mounts and fires its /api/calendar fetch', () => {
    render(<PlannerTab {...makeProps({ plannerMode: 'calendar' })} />);
    expect(global.fetch).toHaveBeenCalledWith('/api/calendar');
  });
});

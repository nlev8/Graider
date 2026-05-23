import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PlannerLesson from '../components/PlannerLesson';

vi.mock('../services/api', () => ({
  generateLessonPlan: vi.fn().mockResolvedValue({ lessonPlan: {} }),
  brainstormLessonIdeas: vi.fn().mockResolvedValue({ ideas: [] }),
  alignDocumentToStandards: vi.fn().mockResolvedValue({}),
  extractTextFromFile: vi.fn().mockResolvedValue({ text: '' }),
  exportGeneratedAssignment: vi.fn().mockResolvedValue({}),
  publishAssignment: vi.fn().mockResolvedValue({}),
  submitAssignment: vi.fn().mockResolvedValue({}),
}));

// Explicit shapes for props the JSX dereferences; everything else (handlers,
// setters) is auto-stubbed as vi.fn() via the Proxy. getDomains/getTotalQuestionCount
// must return real values because the render path calls .map()/arithmetic on them.
const base = () => ({
  config: { subject: 'Math', grade_level: '8', ai_model: 'gpt-4o' },
  unitConfig: { title: '', duration: 1, periodLength: 50, type: 'Lesson Plan', format: 'Word', requirements: '', totalQuestions: 10, questionsPerSection: 0 },
  lessonPlan: null,
  generatedAssignment: null,
  assignment: null,
  standards: [],
  selectedStandards: [],
  uploadedDocs: [],
  domainNameMap: {},
  standardsScrollRef: { current: null },
  // question-editing bundle (from useQuestionEditing, forwarded)
  editMode: false,
  selectedQuestions: new Set(),
  regeneratingQuestions: new Set(),
  editingQuestion: null,
  // lesson state (forwarded; stays in PlannerTab)
  lessonVariations: [],
  brainstormIdeas: [],
  brainstormLoading: false,
  selectedIdea: null,
  expandedStandards: [],
  assignmentSectionsOpen: false,
  assignmentQuestionCounts: {},
  previewResults: null,
  previewShowAnswers: true,
  matchResults: null,
  matchingInProgress: false,
  docUploading: false,
  showSaveLesson: false,
  plannerLoading: false,
  contentOnly: false,
  user: null,
  getDomains: () => [],
  getTotalQuestionCount: () => 0,
});

const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('PlannerLesson', () => {
  it('smoke: renders without crashing (generate UI, no lesson/assignment yet)', () => {
    const { container } = render(<PlannerLesson {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });
});

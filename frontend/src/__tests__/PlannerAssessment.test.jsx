import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PlannerAssessment from '../components/PlannerAssessment';

vi.mock('../services/api', () => ({
  generateAssessment: vi.fn().mockResolvedValue({ assessment: {} }),
  gradeAssessment: vi.fn().mockResolvedValue({}),
  saveAssessment: vi.fn().mockResolvedValue({ status: 'saved' }),
  loadAssessment: vi.fn().mockResolvedValue({}),
  exportGeneratedAssignment: vi.fn().mockResolvedValue({}),
  publishAssessment: vi.fn().mockResolvedValue({}),
}));

// Explicit shapes for props the JSX dereferences; setters/handlers auto-stub via Proxy.
const base = () => ({
  config: { subject: 'Math', grade_level: '8', ai_model: 'gpt-4o' },
  assessmentConfig: { title: '', duration: 1, requirements: '', totalQuestions: 10, questionTypes: {}, format: 'Word', dokDistribution: { 1: 0, 2: 0, 3: 0, 4: 0 }, sources: [] },
  generatedAssessment: null,
  assessmentAnswers: {},
  selectedSources: [],
  selectedStandards: [],
  standards: [],
  savedAssignments: [],
  savedLessons: { units: {} },
  periods: [],
  uploadedDocs: [],
  assessmentLoading: false,
  gradingAssessment: false,
  savingAssessment: false,
  saveAssessmentName: '',
  sectionsDropdownOpen: false,
  // question-editing bundle
  editMode: false,
  selectedQuestions: new Set(),
  regeneratingQuestions: new Set(),
  editingQuestion: null,
  contentOnly: false,
  user: null,
  getDomains: () => [],
  getTotalQuestionCount: () => 0,
});

const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('PlannerAssessment', () => {
  it('smoke: renders without crashing (generate UI, no assessment yet)', () => {
    const { container } = render(<PlannerAssessment {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });

  // Exercises the branches the default smoke test leaves hidden (sections dropdown,
  // content sources, standards list, generated-assessment preview with every
  // question type) so every extracted planner-assessment/* section actually renders.
  it('smoke: renders all guarded sections with real content', () => {
    const props = makeProps({
      previewShowAnswers: false,
      sectionsDropdownOpen: true,
      periods: [{ filename: 'p1.csv', period_name: 'Period 1' }],
      savedLessons: { units: { 'Unit 1': [{ filename: 'l1.json', title: 'Cell Structure' }] } },
      savedAssignments: ['hw-1'],
      savedAssignmentData: { 'hw-1': { title: 'Homework One' } },
      selectedSources: [{ type: 'lesson', unit: 'Unit 1', filename: 'l1.json', title: 'Cell Structure', content: {} }],
      standards: [{ code: 'MA.8.NSO.1.1', dok: 2, benchmark: 'Extend previous understanding of rational numbers.' }],
      selectedStandards: ['MA.8.NSO.1.1'],
      getDomains: () => ['NSO', 'AR'],
      domainNameMap: { NSO: 'Number Sense' },
      assessmentAnswers: { '0-3': 'partial answer' },
      generatedAssessment: {
        title: 'Unit 1 Checkpoint',
        total_points: 30,
        time_limit: 45,
        instructions: 'Answer every question.',
        dok_summary: { dok_1_count: 1, dok_2_count: 2, dok_3_count: 1, dok_4_count: 0 },
        sections: [
          {
            name: 'Section A',
            instructions: 'Choose the best answer.',
            questions: [
              { number: 1, question: 'What is 2+2?', type: 'multiple_choice', options: ['3', '4', '5'], answer: '4', points: 1, dok: 1, standard: 'MA.8.NSO.1.1', warning: 'Distractors look similar', warning_severity: 'info' },
              { number: 2, question: 'The earth is flat.', type: 'true_false', answer: 'False', points: 1, dok: 1 },
              { number: 3, question: 'Match the terms.', type: 'matching', terms: ['Cell'], definitions: ['Basic unit of life'], answer: ['A'], points: 2, dok: 2 },
              { number: 4, question: 'Define osmosis.', type: 'short_answer', points: 2, dok: 2 },
              { number: 5, question: 'Explain photosynthesis.', type: 'extended_response', rubric: 'Full credit for evidence.', points: 4, dok: 3 },
            ],
          },
        ],
      },
    });
    const { container } = render(<PlannerAssessment {...props} />);
    const text = container.textContent;
    // Sidebar cards
    expect(text).toContain('Assessment Settings');
    expect(text).toContain('Assessment Sections');
    expect(text).toContain('Question Types');
    expect(text).toContain('DOK Distribution');
    // Content sources + standards panels
    expect(text).toContain('Cell Structure');
    expect(text).toContain('Homework One');
    expect(text).toContain('MA.8.NSO.1.1');
    expect(text).toContain('Number Sense');
    // Preview header + body
    expect(text).toContain('Unit 1 Checkpoint');
    expect(text).toContain('Grade My Answers');
    expect(text).toContain('Answer every question.');
    expect(text).toContain('Section A');
    // One of each question type rendered with real content
    expect(text).toContain('What is 2+2?');
    expect(text).toContain('Distractors look similar');
    expect(text).toContain('True');
    expect(text).toContain('Basic unit of life');
    expect(text).toContain('Define osmosis.');
    expect(text).toContain('Scoring Criteria');
    expect(text).toContain('Standard: MA.8.NSO.1.1');
    // Short-answer textarea is controlled from assessmentAnswers
    expect(container.querySelector('textarea').value).toBe('partial answer');
  });

  it('smoke: edit mode renders toolbar and question overlays', () => {
    const props = makeProps({
      previewShowAnswers: false,
      editMode: true,
      selectedQuestions: new Set(['0-0']),
      regeneratingQuestions: new Set(),
      editingQuestion: null,
      getTotalQuestionCount: () => 1,
      generatedAssessment: {
        title: 'Edit Me',
        total_points: 10,
        time_limit: null,
        sections: [
          { name: 'Section A', questions: [{ number: 1, question: 'Editable question?', type: 'multiple_choice', options: ['a', 'b'], answer: 'a', points: 1, dok: 1 }] },
        ],
      },
    });
    const { container } = render(<PlannerAssessment {...props} />);
    const text = container.textContent;
    expect(text).toContain('Exit Edit');
    expect(text).toContain('Editable question?');
    expect(text).toContain('1 selected');
  });
});

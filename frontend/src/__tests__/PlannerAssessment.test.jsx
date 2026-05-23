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
});

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

// Mount smoke test for LessonPlanActions and its extracted child
// LessonPlanAssignmentButtons. Added with the CQ wave-8 split (#cq8-07).
// Asserts that key buttons render in each conditional branch without crashing,
// confirming props thread correctly through the child boundary.

vi.mock('../services/api', () => ({
  exportGeneratedAssignment: vi.fn().mockResolvedValue({}),
}));

vi.mock('../components/Icon', () => ({
  default: ({ name }) => <span data-testid={`icon-${name}`} />,
}));

import LessonPlanActions from '../components/planner-lesson/LessonPlanActions';

afterEach(() => {
  vi.clearAllMocks();
});

function baseProps(overrides = {}) {
  return {
    addToast: vi.fn(),
    assignment: { title: '', totalPoints: 100 },
    config: { teacher_name: 'Ms. Smith', subject: 'Math' },
    editMode: false,
    exportLessonPlanHandler: vi.fn(),
    generatedAssignment: null,
    lessonPlan: { title: 'My Lesson', sections: null },
    previewShowAnswers: false,
    publishAssessmentHandler: vi.fn(),
    publishingAssessment: false,
    setActiveTab: vi.fn(),
    setAssignment: vi.fn(),
    setBrainstormIdeas: vi.fn(),
    setEditMode: vi.fn(),
    setEditingQuestion: vi.fn(),
    setGeneratedAssignment: vi.fn(),
    setLessonPlan: vi.fn(),
    setLoadedAssignmentName: vi.fn(),
    setPlannerMode: vi.fn(),
    setPreviewShowAnswers: vi.fn(),
    setSelectedIdea: vi.fn(),
    setSelectedQuestions: vi.fn(),
    setShowSaveLesson: vi.fn(),
    ...overrides,
  };
}

describe('LessonPlanActions mount smoke (renders without crashing)', () => {
  it('renders Export + Save to Unit in plain lesson-plan branch (no sections/days)', () => {
    render(<LessonPlanActions {...baseProps()} />);
    // lesson plan branch: only plain Export button (exportLessonPlanHandler)
    expect(screen.getByText('Export')).toBeTruthy();
    expect(screen.getByText('Save to Unit')).toBeTruthy();
    expect(screen.getByText('Study Guide')).toBeTruthy();
    expect(screen.getByText('Close')).toBeTruthy();
  });

  it('renders LessonPlanAssignmentButtons (Export DOCX, Answer Key, Set Up Grading) when lessonPlan has sections and no days', () => {
    const lessonPlan = {
      title: 'Unit Test',
      sections: [{ name: 'Vocab', points: 20, questions: [{ number: 1, answer: 'A', points: 5 }] }],
    };
    render(<LessonPlanActions {...baseProps({ lessonPlan })} />);
    expect(screen.getByText('Export DOCX')).toBeTruthy();
    expect(screen.getByText('Export PDF')).toBeTruthy();
    expect(screen.getByText('Answer Key')).toBeTruthy();
    expect(screen.getByText('Set Up Grading')).toBeTruthy();
    expect(screen.getByText('Show Answers')).toBeTruthy();
    expect(screen.getByText('Edit Questions')).toBeTruthy();
  });

  it('renders Publish to Portal button when lessonPlan has sections and no phases', () => {
    const lessonPlan = {
      title: 'Unit Test',
      sections: [{ name: 'Vocab', points: 20, questions: [] }],
    };
    render(<LessonPlanActions {...baseProps({ lessonPlan })} />);
    expect(screen.getByText('Publish to Portal')).toBeTruthy();
  });

  it('renders generatedAssignment branch buttons when generatedAssignment is set and lessonPlan has no sections', () => {
    const generatedAssignment = { title: 'Gen Assignment', sections: [] };
    render(
      <LessonPlanActions
        {...baseProps({ generatedAssignment, lessonPlan: { title: 'My Lesson' } })}
      />
    );
    // generatedAssignment branch: Export DOCX, Export PDF, Answer Key, Edit Questions
    expect(screen.getByText('Export DOCX')).toBeTruthy();
    expect(screen.getByText('Export PDF')).toBeTruthy();
    expect(screen.getByText('Answer Key')).toBeTruthy();
    expect(screen.getByText('Edit Questions')).toBeTruthy();
    // no Set Up Grading in this branch
    expect(screen.queryByText('Set Up Grading')).toBeFalsy();
  });

  it('shows "Publishing..." text when publishingAssessment is true', () => {
    const lessonPlan = { title: 'T', sections: [{ name: 'S', points: 10, questions: [] }] };
    render(<LessonPlanActions {...baseProps({ lessonPlan, publishingAssessment: true })} />);
    expect(screen.getByText('Publishing...')).toBeTruthy();
  });

  it('shows "Hide Answers" when previewShowAnswers is true (inside LessonPlanAssignmentButtons)', () => {
    const lessonPlan = { title: 'T', sections: [{ name: 'S', points: 10, questions: [] }] };
    render(<LessonPlanActions {...baseProps({ lessonPlan, previewShowAnswers: true })} />);
    expect(screen.getByText('Hide Answers')).toBeTruthy();
  });

  it('shows "Exit Edit" when editMode is true in generatedAssignment branch', () => {
    const generatedAssignment = { title: 'Gen Assignment' };
    render(
      <LessonPlanActions
        {...baseProps({ generatedAssignment, lessonPlan: { title: 'My Lesson' }, editMode: true })}
      />
    );
    expect(screen.getByText('Exit Edit')).toBeTruthy();
  });
});

import React from 'react';
import { render, screen } from '@testing-library/react';
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

// Added alongside the CQ wave-2 split of PlannerLesson.jsx into
// components/planner-lesson/*. The split relocated ~2,190 lines of JSX into
// 14 child components; the build only proves imports resolve, not that every
// relocated identifier is still in scope at render time. These tests mount
// every branch of the composed tree (sidebar incl. sections config, standards
// selector, brainstorm ideas, variations, day-based lesson plan, project
// phases, assignment-type plan with edit toolbar + player, generated
// assignment panel incl. actions + rubric) so a missed prop surfaces as a
// ReferenceError here instead of in production.
describe('PlannerLesson branch mounts (planner-lesson/* split)', () => {
  const standard = { code: 'MA.8.NSO.1.1', benchmark: 'Number sense and operations' };

  it('mounts sidebar + standards selector with real standards', () => {
    render(
      <PlannerLesson
        {...makeProps({
          standards: [standard],
          unitConfig: { ...base().unitConfig, type: 'Assignment' },
          assignmentSectionsOpen: true,
          assignmentQuestionCounts: { multiple_choice: 3 },
          uploadedDocs: [{ filename: 'notes.pdf', size: 2048 }],
          matchResults: { matched_standards: [{ code: 'MA.8.NSO.1.1', confidence: 0.8 }] },
        })}
      />,
    );
    expect(screen.getByText(/Select Standards/)).toBeTruthy();
    expect(screen.getAllByText(/MA\.8\.NSO\.1\.1/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Brainstorm Assignment Ideas/)).toBeTruthy();
    expect(screen.getByText(/Generate 3 Assignment Variations/)).toBeTruthy();
    expect(screen.getByText(/Reference Documents/)).toBeTruthy();
    expect(screen.getByText('notes.pdf')).toBeTruthy();
    expect(screen.getByText(/Multiple Choice/)).toBeTruthy();
    expect(screen.getByText(/Only create questions from uploaded content/)).toBeTruthy();
  });

  it('mounts brainstorm ideas panel', () => {
    render(
      <PlannerLesson
        {...makeProps({
          brainstormIdeas: [{
            id: 1, title: 'Idea One', approach: 'Project', brief: 'Brief text',
            hook: 'A strong hook', key_activity: 'Group activity', tools_used: 'Desmos',
          }],
        })}
      />,
    );
    expect(screen.getByText('Idea One')).toBeTruthy();
    expect(screen.getAllByText(/Lesson Plan Ideas/).length).toBeGreaterThan(0);
    expect(screen.getByText(/A strong hook/)).toBeTruthy();
    expect(screen.getByText(/Group activity/)).toBeTruthy();
    expect(screen.getByText(/Desmos/)).toBeTruthy();
  });

  it('mounts variations panel with section, phase, and day previews', () => {
    render(
      <PlannerLesson
        {...makeProps({
          lessonVariations: [
            { approach: 'Direct Instruction', title: 'Var A', overview: 'Overview A', days: [{ day: 1 }], essential_questions: ['EQ one', 'EQ two'] },
            { title: 'Var B', overview: 'Overview B', sections: [{ name: 'Sec 1', points: 10, questions: [] }], total_points: 50 },
            { title: 'Var C', overview: 'Overview C', phases: [{ name: 'Phase 1', duration: '2 days' }], total_points: 80 },
          ],
        })}
      />,
    );
    expect(screen.getByText('Var A')).toBeTruthy();
    expect(screen.getByText('Var B')).toBeTruthy();
    expect(screen.getByText('Var C')).toBeTruthy();
    expect(screen.getAllByText(/Use This Lesson Plan/).length).toBe(3);
    expect(screen.getByText(/Sections:/)).toBeTruthy();
    expect(screen.getByText(/Phases:/)).toBeTruthy();
    expect(screen.getByText(/Essential Questions:/)).toBeTruthy();
  });

  it('mounts day-based lesson plan view with actions', () => {
    render(
      <PlannerLesson
        {...makeProps({
          lessonPlan: {
            title: 'Plan T', overview: 'Plan overview',
            days: [{ day: 1, topic: 'Topic One', objective: 'Learn it', bell_ringer: 'BR prompt', activity: 'Main act', assessment: 'Exit ticket' }],
          },
        })}
      />,
    );
    expect(screen.getByText('Plan T')).toBeTruthy();
    expect(screen.getByText('Topic One')).toBeTruthy();
    expect(screen.getByText(/Bell Ringer/)).toBeTruthy();
    expect(screen.getByText(/Main\s*Activity/)).toBeTruthy();
    expect(screen.getByText('BR prompt')).toBeTruthy();
    expect(screen.getByText(/Exit ticket/)).toBeTruthy();
    expect(screen.getByText(/Save to Unit/)).toBeTruthy();
    expect(screen.getByText(/Study Guide/)).toBeTruthy();
    expect(screen.getByText('Export')).toBeTruthy();
  });

  it('mounts project phases view with deliverable and rubric', () => {
    render(
      <PlannerLesson
        {...makeProps({
          lessonPlan: {
            title: 'Proj', overview: 'P overview', driving_question: 'Why does it matter?', total_points: 100,
            phases: [{ phase: 1, name: 'Phase One', duration: '2 days', description: 'Phase desc', tasks: ['Task A'], deliverable: 'Draft' }],
            final_deliverable: { format: 'Poster', requirements: ['Req one'] },
            rubric: { criteria: [{ name: 'Criterion X', points: 10, description: 'Crit desc' }] },
          },
        })}
      />,
    );
    expect(screen.getByText(/Driving Question:/)).toBeTruthy();
    expect(screen.getByText('Phase One')).toBeTruthy();
    expect(screen.getByText('Task A')).toBeTruthy();
    expect(screen.getByText(/Final Deliverable/)).toBeTruthy();
    expect(screen.getByText('Poster')).toBeTruthy();
    expect(screen.getByText('Criterion X')).toBeTruthy();
  });

  it('mounts assignment-type lesson plan with edit toolbar, player, and standards chips', () => {
    render(
      <PlannerLesson
        {...makeProps({
          lessonPlan: {
            title: 'Asmt Plan', overview: 'A overview', total_points: 20,
            sections: [{ name: 'Part A', points: 20, questions: [
              { number: 1, question: 'What is 2+2?', answer: '4', points: 10, question_type: 'short_answer' },
              { number: 2, question: 'What is 3+3?', answer: '6', points: 10, question_type: 'short_answer' },
            ] }],
          },
          editMode: true,
          selectedStandards: ['MA.8.NSO.1.1'],
          standards: [standard],
          getTotalQuestionCount: () => 2,
        })}
      />,
    );
    expect(screen.getAllByText('Asmt Plan').length).toBeGreaterThan(0);
    expect(screen.getByText(/Publish to Portal/)).toBeTruthy();
    expect(screen.getAllByText(/Part A/).length).toBeGreaterThan(0);
    expect(screen.getByText(/What is 2\+2\?/)).toBeTruthy();
    expect(screen.getByText(/Set Up Grading/)).toBeTruthy();
    expect(screen.getByText(/Exit Edit/)).toBeTruthy();
    expect(screen.getByText(/MA\.8\.NSO\.1\.1: Number sense/)).toBeTruthy();
  });

  it('mounts generated assignment panel with actions and rubric', () => {
    render(
      <PlannerLesson
        {...makeProps({
          lessonPlan: {
            title: 'Plan T', overview: 'Plan overview',
            days: [{ day: 1, topic: 'Topic One', objective: 'Learn it' }],
          },
          generatedAssignment: {
            title: 'Gen Quiz', type: 'quiz', time_estimate: '30 min', total_points: 50,
            sections: [{ name: 'GS1', points: 50, questions: [
              { number: 1, question: 'Gen question?', answer: 'Gen answer', points: 50, question_type: 'short_answer' },
            ] }],
            rubric: { criteria: [{ name: 'Gen Criterion', points: 50, description: 'gd' }] },
          },
        })}
      />,
    );
    expect(screen.getAllByText('Gen Quiz').length).toBeGreaterThan(0);
    expect(screen.getByText('Quiz')).toBeTruthy();
    expect(screen.getByText(/30 min/)).toBeTruthy();
    expect(screen.getByText(/Gen question\?/)).toBeTruthy();
    expect(screen.getByText(/Grading Rubric/)).toBeTruthy();
    expect(screen.getByText('Gen Criterion')).toBeTruthy();
    expect(screen.getAllByText(/Set Up Grading/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Answer Key/).length).toBeGreaterThan(0);
  });
});

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import StudentPortal from '../components/StudentPortal';
import * as api from '../services/api';

// Content-asserting mount test for StudentPortal. Added with the CQ wave-6
// split of StudentPortal.jsx into student-portal/* (mirrors
// SettingsAI.mount.test.jsx from wave 5, for the same reason): before this
// test, the only renderers were the no-crash smokes in smoke.test.jsx, which
// pass even if a split leaves an unimported screen component or a
// mis-threaded prop that blanks a stage at runtime. This test drives the
// real stage machine (join → name → assessment → results, plus the material
// stage and the class-based draft-resume path) and asserts real content from
// every extracted screen actually mounts — including the stage==="assessment"
// error banner from PR #740 that the duplicate-submission e2e depends on.

vi.mock('../services/api', () => ({
  getStudentAssessment: vi.fn(),
  submitStudentAssessment: vi.fn(),
  getDraft: vi.fn().mockResolvedValue({ draft: null }),
  saveDraft: vi.fn().mockResolvedValue({}),
}));

beforeEach(() => {
  vi.clearAllMocks();
  api.getDraft.mockResolvedValue({ draft: null });
  api.saveDraft.mockResolvedValue({});
  window.history.pushState({}, '', '/');
  localStorage.clear();
});

const mcAssessment = () => ({
  title: 'Algebra Quiz',
  teacher: 'Ms. Rivera',
  total_points: 5,
  questions: [
    { number: 1, type: 'multiple_choice', question: 'What is 2 + 2?', options: ['3', '4'], points: 5, answer: 'B' },
  ],
});

describe('StudentPortal mounts content from every extracted screen', () => {
  it('drives join -> name -> assessment (incl. #740 error banner) -> results', async () => {
    api.getStudentAssessment.mockResolvedValue(mcAssessment());
    render(<StudentPortal />);

    // JoinScreen
    expect(screen.getByText('Graider')).toBeTruthy();
    expect(screen.getByText('Enter your join code to get started')).toBeTruthy();
    expect(screen.getByText('Join Code')).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText('ABC123'), { target: { value: 'ABC123' } });
    fireEvent.click(screen.getByText('Join'));

    // NameEntryScreen
    expect(await screen.findByText('Algebra Quiz')).toBeTruthy();
    expect(screen.getByText('By Ms. Rivera')).toBeTruthy();
    expect(screen.getByText('Your Name')).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText('Enter your full name'), { target: { value: 'Ada Lovelace' } });
    fireEvent.click(screen.getByText('Start Assessment'));

    // AssessmentScreen — QuestionPlayer mounted with the real question
    // (player renders "1. What is 2 + 2?" — number prefix in the same node)
    expect(await screen.findByText(/What is 2 \+ 2\?/)).toBeTruthy();

    // Duplicate-submission contract (PR #740): a submit error must surface
    // as a banner while stage stays "assessment" (confirm modal has closed).
    api.submitStudentAssessment.mockResolvedValueOnce({ error: 'You have already submitted this assessment.' });
    fireEvent.click(screen.getByTestId('btn-finish'));
    fireEvent.click(await screen.findByTestId('btn-confirm-submit'));
    expect(await screen.findByText('You have already submitted this assessment.')).toBeTruthy();
    // Still on the assessment stage — the player (and its Finish button) remain
    expect(screen.getByTestId('btn-finish')).toBeTruthy();

    // Successful resubmit -> ResultsScreen
    api.submitStudentAssessment.mockResolvedValueOnce({
      score: 4,
      total_points: 5,
      percentage: 80,
      feedback_summary: 'Nice work',
      detailed_results: [
        { number: 1, question: 'What is 2 + 2?', is_correct: true, points_earned: 4, points_possible: 5, student_answer: '4', feedback: 'Correct!' },
      ],
    });
    fireEvent.click(screen.getByTestId('btn-finish'));
    fireEvent.click(await screen.findByTestId('btn-confirm-submit'));
    expect(await screen.findByText('Assessment Complete!')).toBeTruthy();
    expect(screen.getByText('80%')).toBeTruthy();
    expect(screen.getByText('4/5 points')).toBeTruthy();
    expect(screen.getByText('Nice work')).toBeTruthy();
    expect(screen.getByText('Question Review')).toBeTruthy();
    expect(screen.getByText('Correct!')).toBeTruthy();
    expect(screen.getByText('Take Another Assessment')).toBeTruthy();
  });

  it('class-based preloaded path resumes from draft and offers Save for later', async () => {
    api.getDraft.mockResolvedValueOnce({ draft: { answers: { '0-0': 1 }, marked_for_review: [] } });
    render(
      <StudentPortal
        preloadedAssessment={{
          title: 'Cells Quiz',
          sections: [{ name: 'Part A', questions: [{ number: 1, type: 'multiple_choice', question: 'Powerhouse of the cell?', options: ['Nucleus', 'Mitochondria'], points: 5 }] }],
          settings: {},
        }}
        preloadedStudentName="Test Student"
        contentId="content-1"
        studentToken="tok-1"
        preloadedSettings={{}}
      />
    );

    expect(await screen.findByText(/Resumed from draft/)).toBeTruthy();
    expect(screen.getByText(/Powerhouse of the cell\?/)).toBeTruthy();
    expect(screen.getByText('Save for later')).toBeTruthy();
  });

  it('renders the material screen for shared study-guide content', async () => {
    window.history.pushState({}, '', '/join/STUDY1');
    api.getStudentAssessment.mockResolvedValueOnce({
      content_type: 'study_guide',
      title: 'Cell Study Guide',
      teacher: 'Mr. Ray',
      content: 'Mitochondria make ATP.',
    });
    render(<StudentPortal />);

    expect(await screen.findByText('Cell Study Guide')).toBeTruthy();
    expect(screen.getByText('By Mr. Ray')).toBeTruthy();
    expect(screen.getByText('Mitochondria make ATP.')).toBeTruthy();
    expect(screen.getByText('Study More')).toBeTruthy();
  });
});

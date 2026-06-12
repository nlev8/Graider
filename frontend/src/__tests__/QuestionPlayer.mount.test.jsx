import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import QuestionPlayer from '../components/QuestionPlayer';

// Render-time smoke test for QuestionPlayer. Added with the CQ wave-6 split
// of QuestionPlayer.jsx into question-player/* (mirrors the
// AssignmentPlayer.mount.test.jsx from wave 4, added for the same reason):
// build + unit tests pass even if a split leaves an unimported component or
// mis-threaded prop that white-screens the student player at runtime. This
// mounts the real component tree and walks the one-at-a-time flow so every
// extracted piece (PlayerHeader, AccommodationBanner, QuestionPrompt,
// AnswerArea, NavigationButtons, ConfirmSubmitModal, theme, utils) actually
// renders content.

const richSections = () => ([
  {
    name: 'Multiple Choice',
    instructions: 'Pick the best answer.',
    questions: [
      { number: 1, question: 'What is 2 + 2?', type: 'multiple_choice', options: ['Three', 'Four', 'Five'], points: 5, answer: 'B' },
      { number: 2, question: 'The Earth orbits the Sun.', type: 'true_false', points: 5, answer: 'True' },
    ],
  },
  {
    name: 'Open Response',
    instructions: 'Answer in complete sentences.',
    questions: [
      { number: 3, question: 'Explain why the sky is blue.', type: 'short_answer', points: 4 },
    ],
  },
]);

const baseProps = (overrides = {}) => ({
  sections: richSections(),
  contentType: 'assessment',
  settings: {},
  accommodations: [],
  effectiveTimeLimit: null,
  studentName: 'Avery Test',
  title: 'Unit 3 Quiz',
  answers: {},
  onAnswer: vi.fn(),
  onSubmit: vi.fn(),
  loading: false,
  assessment: {},
  studentAccommodation: null,
  ...overrides,
});

describe('QuestionPlayer mounts without crashing (render-time smoke)', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing with empty sections', () => {
    const { container } = render(<QuestionPlayer {...baseProps({ sections: [] })} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders header, section, first question, and Kahoot options', () => {
    const props = baseProps();
    render(<QuestionPlayer {...props} />);

    // PlayerHeader (shell + theme)
    expect(screen.getByText('Unit 3 Quiz')).toBeTruthy();
    expect(screen.getByText('Avery Test')).toBeTruthy();
    expect(screen.getByText('Question 1 of 3')).toBeTruthy();

    // QuestionPrompt — section header + question text + points
    expect(screen.getByText('Multiple Choice')).toBeTruthy();
    expect(screen.getByText('Pick the best answer.')).toBeTruthy();
    expect(screen.getByText('5 points')).toBeTruthy();
    expect(screen.getByText('1. What is 2 + 2?')).toBeTruthy();

    // AnswerArea — Kahoot MC grid (testids pinned by e2e specs)
    expect(screen.getByText('Three')).toBeTruthy();
    expect(screen.getByText('Four')).toBeTruthy();
    fireEvent.click(screen.getByTestId('mc-option-1'));
    expect(props.onAnswer).toHaveBeenCalledWith('0-0', 1);
  });

  it('shows the accommodations banner on question 1', () => {
    render(<QuestionPlayer {...baseProps({
      studentAccommodation: { presets: ['large_text'], custom_notes: 'Sit near the front.' },
    })} />);

    expect(screen.getByText('Your Accommodations')).toBeTruthy();
    expect(screen.getByText('Large Text')).toBeTruthy();
    expect(screen.getByText('Sit near the front.')).toBeTruthy();
  });

  it('navigates TF and text questions, then confirms submit', () => {
    const props = baseProps({
      answers: { '0-0': 1, '0-1': 'True', '1-0': 'Because of light scattering.' },
    });
    render(<QuestionPlayer {...props} />);

    // Q1 answered → Next enabled → Q2 (true/false)
    fireEvent.click(screen.getByTestId('btn-next'));
    expect(screen.getByText('2. The Earth orbits the Sun.')).toBeTruthy();
    expect(screen.getByTestId('tf-option-true')).toBeTruthy();
    expect(screen.getByTestId('tf-option-false')).toBeTruthy();

    // Q3 (short answer, new section)
    fireEvent.click(screen.getByTestId('btn-next'));
    expect(screen.getByText('Open Response')).toBeTruthy();
    expect(screen.getByText('3. Explain why the sky is blue.')).toBeTruthy();
    expect(screen.getByTestId('text-answer').value).toBe('Because of light scattering.');

    // Finish → ConfirmSubmitModal → submit
    fireEvent.click(screen.getByTestId('btn-finish'));
    expect(screen.getByText('Submit?')).toBeTruthy();
    expect(screen.getByText('You answered 3 of 3 questions.')).toBeTruthy();
    fireEvent.click(screen.getByTestId('btn-confirm-submit'));
    expect(props.onSubmit).toHaveBeenCalledTimes(1);
  });
});

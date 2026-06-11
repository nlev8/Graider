import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import AssignmentPlayer from '../components/AssignmentPlayer';

// Render-time smoke test for AssignmentPlayer. Added with the CQ wave-4 split
// of AssignmentPlayer.jsx into assignment-player/* (mirrors the
// GradeTab/AnalyticsTab mount tests from waves 1-2, added for the same
// reason): build + unit tests pass even if a split leaves an unimported
// component or mis-threaded prop that white-screens the student player at
// runtime. This mounts the real component tree with a rich assignment so
// every extracted piece (styles, useVirtualKeyboard, QuestionRenderer,
// RenderQuestionText, MathVisualInput, ChoiceTextInput, BarChartDisplay)
// actually renders content.

const richAssignment = () => ({
  title: 'Unit 3 Checkpoint',
  instructions: 'Answer every question carefully.',
  sections: [
    {
      name: 'Multiple Choice',
      points: 10,
      questions: [
        { question: 'What is 2 + 2?', question_type: 'multiple_choice', options: ['Three', 'Four', 'Five'], points: 5, answer: 'Four' },
        { question: 'The Earth orbits the Sun.', question_type: 'true_false', points: 5 },
      ],
    },
    {
      name: 'Open Response',
      points: 12,
      questions: [
        {
          question: 'Use the table | Shape | Sides |\n|---|---|\n| Triangle | 3 | to answer below.',
          question_type: 'short_answer',
          points: 4,
        },
        { question: 'Plot the point 4 on the number line.', question_type: 'number_line', min_val: 0, max_val: 10, points: 4 },
        {
          question: 'How many students chose pizza?',
          question_type: 'bar_chart',
          chart_data: { title: 'Lunch Votes', labels: ['Pizza', 'Salad'], values: [12, 5], y_label: 'Votes' },
          points: 4,
        },
      ],
    },
  ],
});

describe('AssignmentPlayer mounts without crashing (render-time smoke)', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the empty state without an assignment', () => {
    render(<AssignmentPlayer assignment={null} />);
    expect(screen.getByText('No assignment loaded')).toBeTruthy();
  });

  it('renders header, tabs, and both extracted input groups with a rich assignment', () => {
    render(<AssignmentPlayer assignment={richAssignment()} studentName="Avery Test" />);

    // Header (shell + styles)
    expect(screen.getByText('Unit 3 Checkpoint')).toBeTruthy();
    expect(screen.getByText('Student: Avery Test')).toBeTruthy();
    expect(screen.getByText('0/5 answered')).toBeTruthy();

    // Instructions
    expect(screen.getByText('Answer every question carefully.')).toBeTruthy();

    // Section tabs (tab button + active section heading)
    expect(screen.getAllByText('Multiple Choice')).toHaveLength(2);
    expect(screen.getByText('Open Response')).toBeTruthy();
    expect(screen.getByText('10 pts')).toBeTruthy();

    // Section 1 — QuestionRenderer + ChoiceTextInput (MC + TF)
    expect(screen.getByText('Question 1')).toBeTruthy();
    expect(screen.getByText('What is 2 + 2?')).toBeTruthy();
    expect(screen.getByText('Three')).toBeTruthy();
    expect(screen.getByText('Four')).toBeTruthy();
    expect(screen.getByText('True')).toBeTruthy();
    expect(screen.getByText('False')).toBeTruthy();

    // Answering an MC question routes through useVirtualKeyboard's owner
    // (answers state stays in AssignmentPlayer) and updates progress
    fireEvent.click(screen.getByLabelText('Four'));
    expect(screen.getByText('1/5 answered')).toBeTruthy();

    // Footer
    expect(screen.getByText('Submit Assignment')).toBeTruthy();
    expect(screen.getByText('← Previous')).toBeTruthy();

    // Section 2 — RenderQuestionText markdown table, short answer,
    // MathVisualInput (number line), BarChartDisplay
    fireEvent.click(screen.getByText('Open Response'));
    expect(screen.getByText('Triangle')).toBeTruthy(); // markdown table cell
    expect(screen.getAllByPlaceholderText('Type your answer here...').length).toBeGreaterThan(0);
    expect(screen.getByText('Plot the point 4 on the number line.')).toBeTruthy();
    expect(screen.getByText('Lunch Votes')).toBeTruthy(); // BarChartDisplay title
    expect(screen.getByText('Pizza')).toBeTruthy(); // BarChartDisplay label
  });

  it('renders results, feedback, and the correct answer in review mode', () => {
    const results = {
      score: 8,
      total: 22,
      percent: 36,
      questions: { '0-0': { correct: true, points_earned: 5, feedback: 'Nice work' } },
    };
    render(
      <AssignmentPlayer
        assignment={richAssignment()}
        readOnly={true}
        showAnswers={true}
        results={results}
      />
    );

    expect(screen.getByText('Score:')).toBeTruthy();
    expect(screen.getByText('8/22 (36%)')).toBeTruthy();
    expect(screen.getByText('Nice work')).toBeTruthy();
    expect(screen.getByText('✓ 5/5')).toBeTruthy();
    expect(screen.getByText('Correct Answer:')).toBeTruthy();
  });
});

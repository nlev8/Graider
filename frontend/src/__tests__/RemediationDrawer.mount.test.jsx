import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import RemediationDrawer from '../tabs/RemediationDrawer';

// Content-asserting mount test for RemediationDrawer. Added with the CQ wave-6
// split of RemediationDrawer.jsx into tabs/remediation-drawer/* (mirrors
// SettingsAI.mount.test.jsx / PlannerCalendar branch-mount tests from wave 5,
// for the same reason): `npm run build` only proves imports resolve, not that
// every relocated identifier is still in scope at render time. These tests
// mount every extracted branch (config panel, preview pane with variant tabs
// and question cards, footers, confirm-regen dialog) with real data so a
// missed prop in the split surfaces as a ReferenceError/TypeError here, not
// in production. Written and run GREEN against the pre-split file first.

vi.mock('../services/api', () => ({
  postRemediate: vi.fn(),
  publishToClass: vi.fn(),
  publishToClassBatch: vi.fn(),
}));

import * as api from '../services/api';

const makeProps = (overrides = {}) => ({
  open: true,
  onClose: vi.fn(),
  classId: 'class-1',
  standardCode: 'MATH.7.EE.1',
  targetMode: 'red_tier',
  targetStudentId: null,
  targetStudentName: null,
  onPublished: vi.fn(),
  ...overrides,
});

const sharedResponse = {
  mode: 'shared',
  target_student_ids: ['s1', 's2', 's3'],
  lesson: { intro: 'Lesson intro text here.' },
  questions: [
    { text: 'What is 2 + 2?', type: 'mcq', choices: ['3', '4', '5'], correct_answer: 1 },
    { text: 'Explain your reasoning.', type: 'short_answer' },
  ],
};

const personalizedResponse = {
  mode: 'personalized',
  variants: [
    {
      student_id: 's1', student_name: 'Ada Lovelace',
      questions: [{ text: 'Ada question one?', type: 'short_answer' }],
    },
    {
      student_id: 's2', student_name: 'Alan Turing',
      questions: [{ text: 'Alan question one?', type: 'short_answer' }],
    },
  ],
};

describe('RemediationDrawer mounts with content from every extracted section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.postRemediate.mockResolvedValue(sharedResponse);
    api.publishToClass.mockResolvedValue({ status: 'published' });
    api.publishToClassBatch.mockResolvedValue({ status: 'published' });
  });

  it('open=false renders nothing', () => {
    const { container } = render(<RemediationDrawer {...makeProps({ open: false })} />);
    expect(container.firstChild).toBeNull();
  });

  it('opens to the config state: header, count slider, difficulty + DOK toggles, footer', () => {
    render(<RemediationDrawer {...makeProps()} />);
    // Header
    expect(screen.getByText('Remediation: MATH.7.EE.1')).toBeTruthy();
    // ConfigPanel content
    expect(screen.getByText('Configure remediation')).toBeTruthy();
    expect(screen.getByText(/Question count:/)).toBeTruthy();
    expect(screen.getByRole('slider')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'easier' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'same' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'harder' })).toBeTruthy();
    expect(screen.getByText('Cognitive demand (DOK)')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Auto' })).toBeTruthy();
    expect(screen.getByText('Grade-level review.')).toBeTruthy();
    // Config footer
    expect(screen.getByRole('button', { name: 'Generate' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();
  });

  it('config controls update: difficulty + DOK selection change helper text', () => {
    render(<RemediationDrawer {...makeProps()} />);
    fireEvent.click(screen.getByRole('button', { name: 'easier' }));
    expect(screen.getByText('Simpler vocabulary, more scaffolding.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '3' }));
    expect(screen.getByText('DOK 3 — Strategic Thinking.')).toBeTruthy();
  });

  it('Generate posts config payload and renders the shared preview (lesson, question cards, footer)', async () => {
    render(<RemediationDrawer {...makeProps()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    expect(api.postRemediate).toHaveBeenCalledWith('class-1', {
      standard_code: 'MATH.7.EE.1',
      target_mode: 'red_tier',
      count: 8,
      difficulty: 'same',
      dok: null,
    });
    // PreviewPane: lesson block + question cards with editable content
    await screen.findByText('Q1');
    expect(screen.getByText('Lesson intro text here.')).toBeTruthy();
    expect(screen.getByDisplayValue('What is 2 + 2?')).toBeTruthy();
    expect(screen.getByDisplayValue('4')).toBeTruthy(); // MC choice input
    expect(screen.getByText('Q2')).toBeTruthy();
    expect(screen.getByDisplayValue('Explain your reasoning.')).toBeTruthy();
    // Preview footer: subtitle + publish target count from target_student_ids
    expect(screen.getByText('for 3 red-tier students')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Publish to 3' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Adjust settings' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Regenerate all' })).toBeTruthy();
  });

  it('personalized mode renders variant tabs and switches the active preview', async () => {
    api.postRemediate.mockResolvedValue(personalizedResponse);
    render(<RemediationDrawer {...makeProps()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    await screen.findByRole('button', { name: 'Ada Lovelace' });
    expect(screen.getByRole('button', { name: 'Alan Turing' })).toBeTruthy();
    // First variant's questions visible
    expect(screen.getByDisplayValue('Ada question one?')).toBeTruthy();
    expect(screen.queryByDisplayValue('Alan question one?')).toBeNull();
    // Switch tab
    fireEvent.click(screen.getByRole('button', { name: 'Alan Turing' }));
    expect(screen.getByDisplayValue('Alan question one?')).toBeTruthy();
    expect(screen.queryByDisplayValue('Ada question one?')).toBeNull();
    // Personalized subtitle
    expect(screen.getByText('for 2 students (personalized)')).toBeTruthy();
  });

  it('Regenerate all opens the confirm dialog; Keep editing dismisses it', async () => {
    render(<RemediationDrawer {...makeProps()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    await screen.findByText('Q1');
    fireEvent.click(screen.getByRole('button', { name: 'Regenerate all' }));
    expect(screen.getByText('Regenerate all questions?')).toBeTruthy();
    expect(screen.getByText("Any edits you've made will be lost.")).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
    expect(screen.queryByText('Regenerate all questions?')).toBeNull();
  });

  it('Publish (shared) calls publishToClass with lesson round-trip and shows success', async () => {
    const props = makeProps();
    render(<RemediationDrawer {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    await screen.findByText('Q1');
    fireEvent.click(screen.getByRole('button', { name: 'Publish to 3' }));
    await waitFor(() => expect(api.publishToClass).toHaveBeenCalled());
    expect(api.publishToClass).toHaveBeenCalledWith(
      'class-1',
      { questions: sharedResponse.questions, lesson: sharedResponse.lesson },
      'assessment',
      'Remediation: MATH.7.EE.1',
      { target_standard: 'MATH.7.EE.1' },
      null,
      ['s1', 's2', 's3'],
    );
    await screen.findByText('Published to 3 students.');
    expect(props.onPublished).toHaveBeenCalled();
  });

  it('Publish (personalized) batches one item per variant', async () => {
    api.postRemediate.mockResolvedValue(personalizedResponse);
    render(<RemediationDrawer {...makeProps()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    await screen.findByRole('button', { name: 'Ada Lovelace' });
    fireEvent.click(screen.getByRole('button', { name: 'Publish to 2' }));
    await waitFor(() => expect(api.publishToClassBatch).toHaveBeenCalled());
    const [classId, items, contentType] = api.publishToClassBatch.mock.calls[0];
    expect(classId).toBe('class-1');
    expect(contentType).toBe('assessment');
    expect(items).toHaveLength(2);
    expect(items[0].target_student_ids).toEqual(['s1']);
    expect(items[1].target_student_ids).toEqual(['s2']);
    expect(items[0].title).toBe('Remediation: MATH.7.EE.1');
    await screen.findByText('Published to 2 students.');
  });

  it('validation failure shows inline banner and does not publish', async () => {
    api.postRemediate.mockResolvedValue({
      mode: 'shared',
      target_student_ids: ['s1'],
      questions: [{ text: 'Pick one', type: 'mcq', choices: ['only one'], correct_answer: 0 }],
    });
    render(<RemediationDrawer {...makeProps()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    await screen.findByText('Q1');
    fireEvent.click(screen.getByRole('button', { name: 'Publish to 1' }));
    expect(await screen.findByText('Question 1 needs at least 2 choices')).toBeTruthy();
    expect(api.publishToClass).not.toHaveBeenCalled();
  });

  it('generation error renders the error state with Retry', async () => {
    api.postRemediate.mockRejectedValue(new Error('boom'));
    render(<RemediationDrawer {...makeProps()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    expect(await screen.findByText('boom')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeTruthy();
  });

  it('Adjust settings returns to config; Cancel there restores the preview', async () => {
    render(<RemediationDrawer {...makeProps()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }));
    await screen.findByText('Q1');
    fireEvent.click(screen.getByRole('button', { name: 'Adjust settings' }));
    expect(screen.getByText('Configure remediation')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByText('Q1')).toBeTruthy(); // preview preserved, not closed
  });
});

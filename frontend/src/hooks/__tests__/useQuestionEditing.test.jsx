import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useQuestionEditing } from '../useQuestionEditing';

// The handlers consume `data.replacements` (the backend's shape), not `data.questions`.
vi.mock('../../services/api', () => ({
  regenerateQuestions: vi.fn().mockResolvedValue({
    replacements: [{ section_index: 0, question_index: 0, question: { question: 'regenerated', points: 1 } }],
    usage: { cost_display: null },
  }),
}));

const makeInputs = (over = {}) => ({
  getActiveAssignment: vi.fn(() => ({
    sections: [{ name: 'S1', points: 2, questions: [{ question: 'q1', points: 1 }, { question: 'q2', points: 1 }] }],
  })),
  setActiveAssignment: vi.fn(),
  addToast: vi.fn(),
  config: { ai_model: 'gpt-4o', subject: 'Math', grade_level: '8' },
  unitConfig: {},
  ...over,
});

describe('useQuestionEditing', () => {
  it('initial state: editMode false, empty selection', () => {
    const { result } = renderHook(() => useQuestionEditing(makeInputs()));
    expect(result.current.editMode).toBe(false);
    expect(result.current.selectedQuestions.size).toBe(0);
  });

  it('toggleQuestionSelect toggles a key in selectedQuestions', () => {
    const { result } = renderHook(() => useQuestionEditing(makeInputs()));
    act(() => result.current.toggleQuestionSelect('0-0'));
    expect(result.current.selectedQuestions.has('0-0')).toBe(true);
    act(() => result.current.toggleQuestionSelect('0-0'));
    expect(result.current.selectedQuestions.has('0-0')).toBe(false);
  });

  it('saveEditedQuestion writes the active assignment back via setActiveAssignment', () => {
    const setActiveAssignment = vi.fn();
    const { result } = renderHook(() => useQuestionEditing(makeInputs({ setActiveAssignment })));
    act(() => result.current.saveEditedQuestion(0, 0, { question: 'edited', points: 1 }));
    expect(setActiveAssignment).toHaveBeenCalled();
  });

  it('regenerateOneQuestion calls api.regenerateQuestions and writes the result back', async () => {
    const api = await import('../../services/api');
    const setActiveAssignment = vi.fn();
    const { result } = renderHook(() => useQuestionEditing(makeInputs({ setActiveAssignment })));
    await act(async () => { await result.current.regenerateOneQuestion(0, 0); });
    expect(api.regenerateQuestions).toHaveBeenCalled();
    expect(setActiveAssignment).toHaveBeenCalled();
  });
});

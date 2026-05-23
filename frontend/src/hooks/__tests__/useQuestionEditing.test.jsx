import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useQuestionEditing } from '../useQuestionEditing';

vi.mock('../../services/api', () => ({
  regenerateQuestions: vi.fn().mockResolvedValue({ questions: [{ question: 'regenerated' }] }),
}));

const makeInputs = (over = {}) => ({
  getActiveAssignment: vi.fn(() => ({
    sections: [{ name: 'S1', questions: [{ question: 'q1' }, { question: 'q2' }] }],
  })),
  setActiveAssignment: vi.fn(),
  addToast: vi.fn(),
  config: { ai_model: 'gpt-4o', subject: 'Math', grade_level: '8' },
  unitConfig: {},
  globalAINotes: '',
  standards: [],
  selectedStandards: [],
  uploadedDocs: [],
  setUploadedDocs: vi.fn(),
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
    act(() => result.current.saveEditedQuestion(0, 0, { question: 'edited' }));
    expect(setActiveAssignment).toHaveBeenCalled();
  });

  it('regenerateOneQuestion calls api.regenerateQuestions', async () => {
    const api = await import('../../services/api');
    const { result } = renderHook(() => useQuestionEditing(makeInputs()));
    await act(async () => { await result.current.regenerateOneQuestion(0, 0); });
    expect(api.regenerateQuestions).toHaveBeenCalled();
  });
});

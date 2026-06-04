import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../services/api', () => ({
  saveAssessmentLocally: vi.fn(),
  listSavedAssessments: vi.fn(),
  loadSavedAssessment: vi.fn(),
  deleteSavedAssessment: vi.fn(),
  gradeAssessmentAnswers: vi.fn(),
  listLessons: vi.fn(),
}));

import * as api from '../../services/api';
import { useSavedAssessmentActions } from '../useSavedAssessmentActions';

// Characterization net for the App.jsx -> useSavedAssessmentActions extraction (slice 17).
// Pins save (guards + persist + internal list refresh), fetch, load, delete (confirm +
// internal refresh), grade, and the saved-lessons fetch.
function setup(over = {}) {
  const fns = {};
  for (const s of [
    'addToast', 'setSavingAssessment', 'setSaveAssessmentName', 'setSavedLessons',
    'setLoadingSavedAssessments', 'setSavedAssessments', 'setGeneratedAssessment',
    'setAssessmentAnswers', 'setAssessmentGradingResults', 'setGradingAssessment',
  ]) fns[s] = vi.fn();
  const props = {
    generatedAssessment: { title: 'Quiz', total_points: 10 },
    saveAssessmentName: 'My Quiz',
    assessmentAnswers: { 0: 'a' },
    ...fns,
    ...over,
  };
  const { result } = renderHook(() => useSavedAssessmentActions(props));
  return { result, props };
}

describe('useSavedAssessmentActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.saveAssessmentLocally.mockResolvedValue({ success: true });
    api.listSavedAssessments.mockResolvedValue({ assessments: [{ name: 'Quiz' }] });
    api.loadSavedAssessment.mockResolvedValue({ assessment: { title: 'Quiz', time_estimate: '20 min' } });
    api.deleteSavedAssessment.mockResolvedValue({ success: true });
    api.gradeAssessmentAnswers.mockResolvedValue({ results: { score: 8, total_points: 10, percentage: 80 } });
    api.listLessons.mockResolvedValue({ units: { U1: {} } });
  });

  it('save: blocks without a name', async () => {
    const { result, props } = setup({ saveAssessmentName: '   ' });
    await result.current.saveAssessmentHandler();
    expect(props.addToast).toHaveBeenCalledWith('Please enter a name for the assessment', 'warning');
    expect(api.saveAssessmentLocally).not.toHaveBeenCalled();
  });

  it('save: persists, clears the name, and refreshes the list (internal cross-call)', async () => {
    const { result, props } = setup();
    await result.current.saveAssessmentHandler();
    expect(api.saveAssessmentLocally).toHaveBeenCalledWith({ title: 'Quiz', total_points: 10 }, 'My Quiz');
    expect(props.setSaveAssessmentName).toHaveBeenCalledWith('');
    expect(api.listSavedAssessments).toHaveBeenCalled(); // fetchSavedAssessments fired
  });

  it('load: stores the assessment + derives a time_limit', async () => {
    const { result, props } = setup();
    await result.current.loadSavedAssessment('Quiz.json');
    expect(props.setGeneratedAssessment).toHaveBeenCalledWith(expect.objectContaining({ title: 'Quiz', time_limit: 20 }));
    expect(props.addToast).toHaveBeenCalledWith('Assessment loaded!', 'success');
  });

  it('delete: confirm-gated; on confirm deletes + refreshes', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { result } = setup();
    await result.current.deleteSavedAssessment('Quiz.json');
    expect(api.deleteSavedAssessment).toHaveBeenCalledWith('Quiz.json');
    expect(api.listSavedAssessments).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('grade: blocks without answers, else grades and stores results', async () => {
    const blocked = setup({ assessmentAnswers: {} });
    await blocked.result.current.gradeAssessmentAnswersHandler();
    expect(blocked.props.addToast).toHaveBeenCalledWith('Please answer at least one question first', 'warning');

    const { result, props } = setup();
    await result.current.gradeAssessmentAnswersHandler();
    expect(api.gradeAssessmentAnswers).toHaveBeenCalled();
    expect(props.setAssessmentGradingResults).toHaveBeenCalledWith({ score: 8, total_points: 10, percentage: 80 });
  });

  it('fetchSavedAssessments / fetchSavedLessons store their lists', async () => {
    const { result, props } = setup();
    await result.current.fetchSavedAssessments();
    expect(props.setSavedAssessments).toHaveBeenCalledWith([{ name: 'Quiz' }]);
    await result.current.fetchSavedLessons();
    expect(props.setSavedLessons).toHaveBeenCalledWith({ units: { U1: {} } });
  });
});

import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../services/api', () => ({
  saveAssignmentConfig: vi.fn(),
  listAssignments: vi.fn(),
  loadAssignment: vi.fn(),
  deleteAssignment: vi.fn(),
  exportAssignment: vi.fn(),
}));

import * as api from '../../services/api';
import { useAssignmentBuilderActions } from '../useAssignmentBuilderActions';

// Characterization net for the App.jsx -> useAssignmentBuilderActions extraction (slice 10).
// Pins the 4 Builder CRUD handlers: save (title guard + happy + list refresh), load
// (stores the assignment + name + toggles loading), delete (confirm guard + filter), export.
function setup(over = {}) {
  const fns = {
    addToast: vi.fn(),
    setAssignment: vi.fn(),
    setImportedDoc: vi.fn(),
    setDocEditorModal: vi.fn(),
    setLoadedAssignmentName: vi.fn(),
    setSavedAssignments: vi.fn(),
    setSavedAssignmentData: vi.fn(),
    setIsLoadingAssignment: vi.fn(),
    textToRichHtml: vi.fn((t) => '<p>' + t + '</p>'),
  };
  const props = {
    assignment: { title: 'Quiz' },
    savedAssignments: ['Quiz', 'Old'],
    loadedAssignmentName: '',
    docEditorModal: {},
    importedDoc: { text: '', html: '' },
    skipAutoSaveRef: { current: false },
    ...fns,
    ...over,
  };
  const { result } = renderHook(() => useAssignmentBuilderActions(props));
  return { result, props };
}

describe('useAssignmentBuilderActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.saveAssignmentConfig.mockResolvedValue({ status: 'saved' });
    api.listAssignments.mockResolvedValue({ assignments: ['Quiz'], assignmentData: { Quiz: {} } });
    api.loadAssignment.mockResolvedValue({ assignment: { title: 'Loaded' } });
    api.deleteAssignment.mockResolvedValue({});
    api.exportAssignment.mockResolvedValue({ document: 'x' });
  });

  it('save: blocks (warns, no API) when the title is empty', async () => {
    const { result, props } = setup({ assignment: { title: '' } });
    await result.current.saveAssignmentConfig();
    expect(props.addToast).toHaveBeenCalledWith('Please enter a title', 'warning');
    expect(api.saveAssignmentConfig).not.toHaveBeenCalled();
  });

  it('save: persists, toasts, sets loaded name, and refreshes the list', async () => {
    const { result, props } = setup();
    await result.current.saveAssignmentConfig();
    expect(api.saveAssignmentConfig).toHaveBeenCalledWith({ title: 'Quiz', importedDoc: { text: '', html: '' } });
    expect(props.addToast).toHaveBeenCalledWith('Assignment saved!', 'success');
    expect(props.setLoadedAssignmentName).toHaveBeenCalledWith('Quiz');
    expect(api.listAssignments).toHaveBeenCalled();
    expect(props.setSavedAssignments).toHaveBeenCalledWith(['Quiz']);
  });

  it('load: fetches, sets the assignment + loaded name, and guards autosave', async () => {
    vi.useFakeTimers();
    const { result, props } = setup();
    await result.current.loadAssignment('Loaded');
    expect(props.skipAutoSaveRef.current).toBe(true);
    expect(props.setIsLoadingAssignment).toHaveBeenCalledWith(true);
    expect(props.setAssignment).toHaveBeenCalled();
    expect(props.setLoadedAssignmentName).toHaveBeenCalledWith('Loaded');
    vi.advanceTimersByTime(500);
    expect(props.setIsLoadingAssignment).toHaveBeenCalledWith(false);
    vi.useRealTimers();
  });

  it('delete: aborts when not confirmed', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    const { result } = setup();
    await result.current.deleteAssignment('Old');
    expect(api.deleteAssignment).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('delete: removes from the list and toasts when confirmed', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { result, props } = setup();
    await result.current.deleteAssignment('Old');
    expect(api.deleteAssignment).toHaveBeenCalledWith('Old');
    expect(props.setSavedAssignments).toHaveBeenCalledWith(['Quiz']); // 'Old' filtered out
    expect(props.addToast).toHaveBeenCalledWith('"Old" deleted', 'success');
    confirmSpy.mockRestore();
  });

  it('export: calls the API and toasts success', async () => {
    const { result, props } = setup({ assignment: { title: 'Quiz', questions: [{ q: 1 }] } });
    await result.current.exportAssignment('docx');
    expect(api.exportAssignment).toHaveBeenCalledWith({
      assignment: { title: 'Quiz', questions: [{ q: 1 }] },
      format: 'docx',
    });
    expect(props.addToast).toHaveBeenCalledWith('Assignment exported!', 'success');
  });
});

import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../services/api', () => ({
  saveAssignmentConfig: vi.fn(),
  deleteAssignment: vi.fn(),
  listAssignments: vi.fn(),
}));

import * as api from '../../services/api';
import { useAssignmentAutoSave } from '../useAssignmentAutoSave';

// Characterization net for the App.jsx -> useAssignmentAutoSave extraction (slice 5).
// Pins the debounced Builder auto-save: the four early-return guards, the happy-path
// save + loaded-name update, and the rename -> alias/delete/list-refresh path.
function run(overrides = {}) {
  const props = {
    assignment: { title: 'Quiz 1' },
    setAssignment: vi.fn(),
    importedDoc: {},
    settingsLoaded: true,
    loadedAssignmentName: '',
    setLoadedAssignmentName: vi.fn(),
    isLoadingAssignment: false,
    skipAutoSaveRef: { current: false },
    setSavedAssignments: vi.fn(),
    setSavedAssignmentData: vi.fn(),
    addToast: vi.fn(),
    ...overrides,
  };
  renderHook(() => useAssignmentAutoSave(props));
  return props;
}

describe('useAssignmentAutoSave', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    api.saveAssignmentConfig.mockResolvedValue({ status: 'saved' });
    api.deleteAssignment.mockResolvedValue({});
    api.listAssignments.mockResolvedValue({ assignments: ['Quiz 1'], assignmentData: { Quiz1: {} } });
  });
  afterEach(() => { vi.useRealTimers(); });

  it('debounce-saves after 1.5s and updates the loaded name (non-rename)', async () => {
    const props = run();
    await vi.advanceTimersByTimeAsync(1500);
    expect(api.saveAssignmentConfig).toHaveBeenCalledWith({ title: 'Quiz 1', importedDoc: {} });
    expect(props.setLoadedAssignmentName).toHaveBeenCalledWith('Quiz 1');
    expect(props.setSavedAssignmentData).toHaveBeenCalled(); // local card update, no full refresh
    expect(api.listAssignments).not.toHaveBeenCalled();
  });

  it('does not save until settings are loaded', async () => {
    run({ settingsLoaded: false });
    await vi.advanceTimersByTimeAsync(2000);
    expect(api.saveAssignmentConfig).not.toHaveBeenCalled();
  });

  it('does not save an assignment without a title', async () => {
    run({ assignment: { title: '' } });
    await vi.advanceTimersByTimeAsync(2000);
    expect(api.saveAssignmentConfig).not.toHaveBeenCalled();
  });

  it('does not save while an assignment is loading', async () => {
    run({ isLoadingAssignment: true });
    await vi.advanceTimersByTimeAsync(2000);
    expect(api.saveAssignmentConfig).not.toHaveBeenCalled();
  });

  it('consumes the skip ref once after a load and does not save', async () => {
    const skipAutoSaveRef = { current: true };
    run({ skipAutoSaveRef });
    expect(skipAutoSaveRef.current).toBe(false); // reset
    await vi.advanceTimersByTimeAsync(2000);
    expect(api.saveAssignmentConfig).not.toHaveBeenCalled();
  });

  it('on rename: writes the old name as an alias, deletes the old file, refreshes the list', async () => {
    const props = run({ loadedAssignmentName: 'Old Name', assignment: { title: 'New Name', aliases: [] } });
    await vi.advanceTimersByTimeAsync(1500);
    const saved = api.saveAssignmentConfig.mock.calls[0][0];
    expect(saved.aliases).toContain('Old Name');
    expect(api.deleteAssignment).toHaveBeenCalledWith('Old Name');
    expect(api.listAssignments).toHaveBeenCalled();
    expect(props.setSavedAssignments).toHaveBeenCalledWith(['Quiz 1']);
  });

  it('toasts on a save error', async () => {
    api.saveAssignmentConfig.mockResolvedValue({ error: 'disk full' });
    const props = run();
    await vi.advanceTimersByTimeAsync(1500);
    expect(props.addToast).toHaveBeenCalledWith('Failed to save assignment: disk full', 'error');
  });
});

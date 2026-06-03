import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../services/api', () => ({ updateResult: vi.fn() }));

import * as api from '../../services/api';
import { useEditedResultsAutoSave } from '../useEditedResultsAutoSave';

// Characterization net for the App.jsx -> useEditedResultsAutoSave extraction (slice 8).
// Pins the debounced save of inline result edits: only items flagged edited+filename
// are persisted, the edited flag is cleared on success, and empty/no-edits are no-ops.
describe('useEditedResultsAutoSave', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    api.updateResult.mockResolvedValue({});
  });
  afterEach(() => vi.useRealTimers());

  it('does nothing when there are no results', async () => {
    renderHook(() => useEditedResultsAutoSave({ editedResults: [], setEditedResults: vi.fn() }));
    await vi.advanceTimersByTimeAsync(2000);
    expect(api.updateResult).not.toHaveBeenCalled();
  });

  it('does nothing when no result is flagged edited', async () => {
    renderHook(() => useEditedResultsAutoSave({
      editedResults: [{ filename: 'a.docx', edited: false }],
      setEditedResults: vi.fn(),
    }));
    await vi.advanceTimersByTimeAsync(2000);
    expect(api.updateResult).not.toHaveBeenCalled();
  });

  it('persists edited items after the 1s debounce and clears the edited flag', async () => {
    const setEditedResults = vi.fn();
    renderHook(() => useEditedResultsAutoSave({
      editedResults: [{ filename: 'a.docx', edited: true, score: 90, letter_grade: 'A', feedback: 'good' }],
      setEditedResults,
    }));
    expect(api.updateResult).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1000);
    expect(api.updateResult).toHaveBeenCalledWith('a.docx', { score: 90, letter_grade: 'A', feedback: 'good' });
    // The clear-flag updater must clear ONLY the matching item's `edited` flag.
    const updater = setEditedResults.mock.calls[0][0];
    const next = updater([
      { filename: 'a.docx', edited: true, score: 90 },
      { filename: 'other.docx', edited: true, score: 50 },
    ]);
    expect(next).toEqual([
      { filename: 'a.docx', edited: false, score: 90 },     // cleared
      { filename: 'other.docx', edited: true, score: 50 },  // untouched (different filename)
    ]);
  });

  it('only persists items that have a filename', async () => {
    renderHook(() => useEditedResultsAutoSave({
      editedResults: [
        { edited: true, score: 1 },                 // no filename -> skipped
        { filename: 'b.docx', edited: true, score: 2 },
      ],
      setEditedResults: vi.fn(),
    }));
    await vi.advanceTimersByTimeAsync(1000);
    expect(api.updateResult).toHaveBeenCalledTimes(1);
    expect(api.updateResult).toHaveBeenCalledWith('b.docx', expect.objectContaining({ score: 2 }));
  });
});

import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as api from '../../services/api';
import { useSettingsAutoSave } from '../useSettingsAutoSave';

vi.mock('../../services/api', () => ({
  saveGlobalSettings: vi.fn(() => Promise.resolve()),
  saveRubric: vi.fn(() => Promise.resolve()),
}));

const props = (over = {}) => ({ config: { a: 1 }, globalAINotes: 'n', rubric: { r: 1 }, settingsLoaded: true, ...over });

describe('useSettingsAutoSave', () => {
  beforeEach(() => { vi.useFakeTimers(); api.saveGlobalSettings.mockClear(); api.saveRubric.mockClear(); });
  afterEach(() => { vi.useRealTimers(); });

  it('does not save before settingsLoaded', () => {
    renderHook(() => useSettingsAutoSave(props({ settingsLoaded: false })));
    vi.advanceTimersByTime(2000);
    expect(api.saveGlobalSettings).not.toHaveBeenCalled();
    expect(api.saveRubric).not.toHaveBeenCalled();
  });

  it('debounces: does not save before 1000ms, saves after', () => {
    renderHook(() => useSettingsAutoSave(props()));
    vi.advanceTimersByTime(900);
    expect(api.saveGlobalSettings).not.toHaveBeenCalled();
    vi.advanceTimersByTime(200);
    expect(api.saveGlobalSettings).toHaveBeenCalledWith({ globalAINotes: 'n', config: { a: 1 } });
    expect(api.saveRubric).toHaveBeenCalledWith({ r: 1 });
  });

  it('re-saves when config changes (debounced)', () => {
    const { rerender } = renderHook((p) => useSettingsAutoSave(p), { initialProps: props() });
    vi.advanceTimersByTime(1000);
    expect(api.saveGlobalSettings).toHaveBeenCalledTimes(1);
    rerender(props({ config: { a: 2 } }));
    vi.advanceTimersByTime(1000);
    expect(api.saveGlobalSettings).toHaveBeenCalledTimes(2);
  });

  it('re-saves when rubric changes (debounced)', () => {
    const { rerender } = renderHook((p) => useSettingsAutoSave(p), { initialProps: props() });
    vi.advanceTimersByTime(1000);
    expect(api.saveRubric).toHaveBeenCalledTimes(1);
    rerender(props({ rubric: { r: 2 } }));
    vi.advanceTimersByTime(1000);
    expect(api.saveRubric).toHaveBeenCalledTimes(2);
  });
});

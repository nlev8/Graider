import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useToasts } from '../useToasts';

// Characterization net for the App.jsx -> useToasts extraction (slice 2).
// Pins the exact behavior the verbatim move must preserve: add returns an
// incrementing id and appends {id,message,type}, auto-dismiss after `duration`,
// duration 0/null persists, remove filters by id, and setToasts is exposed
// (App's grading-status effect mutates a live toast in place via it).
describe('useToasts', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('starts empty', () => {
    const { result } = renderHook(() => useToasts());
    expect(result.current.toasts).toEqual([]);
  });

  it('addToast appends {id, message, type} and returns the id', () => {
    const { result } = renderHook(() => useToasts());
    let id;
    act(() => { id = result.current.addToast('Saved', 'success'); });
    expect(id).toBe(1);
    expect(result.current.toasts).toEqual([{ id: 1, message: 'Saved', type: 'success' }]);
  });

  it('defaults type to "success" and increments ids', () => {
    const { result } = renderHook(() => useToasts());
    act(() => { result.current.addToast('a'); });
    act(() => { result.current.addToast('b', 'error'); });
    expect(result.current.toasts.map((t) => [t.id, t.type])).toEqual([[1, 'success'], [2, 'error']]);
  });

  it('auto-dismisses after the given duration', () => {
    const { result } = renderHook(() => useToasts());
    act(() => { result.current.addToast('temp', 'info', 4000); });
    expect(result.current.toasts).toHaveLength(1);
    act(() => { vi.advanceTimersByTime(4000); });
    expect(result.current.toasts).toHaveLength(0);
  });

  it('duration 0 persists (no auto-dismiss)', () => {
    const { result } = renderHook(() => useToasts());
    act(() => { result.current.addToast('sticky', 'warning', 0); });
    act(() => { vi.advanceTimersByTime(100000); });
    expect(result.current.toasts).toHaveLength(1);
  });

  it('removeToast removes by id', () => {
    const { result } = renderHook(() => useToasts());
    let id;
    act(() => { id = result.current.addToast('x', 'info', 0); });
    act(() => { result.current.removeToast(id); });
    expect(result.current.toasts).toHaveLength(0);
  });

  it('exposes setToasts for the external grading-status mutator', () => {
    const { result } = renderHook(() => useToasts());
    act(() => { result.current.addToast('g', 'info', 0); });
    act(() => {
      result.current.setToasts((prev) => prev.map((t) => ({ ...t, message: 'updated' })));
    });
    expect(result.current.toasts[0].message).toBe('updated');
  });
});

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as api from '../../services/api';
import { useFocusPolling } from '../useFocusPolling';

vi.mock('../../services/api', () => ({ getFocusCommsStatus: vi.fn(), getFocusCommentsStatus: vi.fn() }));

describe('useFocusPolling', () => {
  beforeEach(() => { vi.useFakeTimers(); api.getFocusCommsStatus.mockReset(); api.getFocusCommentsStatus.mockReset(); });
  afterEach(() => { vi.useRealTimers(); });

  it('starts idle, not polling, and exposes the setter bundle', () => {
    const { result } = renderHook(() => useFocusPolling(vi.fn()));
    expect(result.current.focusCommsStatus.status).toBe('idle');
    expect(result.current.focusCommsPolling).toBe(false);
    ['setFocusCommsStatus','setFocusCommsPolling','setFocusCommentsStatus','setFocusCommentsPolling']
      .forEach(k => expect(typeof result.current[k]).toBe('function'));
  });

  it('does not poll while the comms flag is false', () => {
    renderHook(() => useFocusPolling(vi.fn()));
    vi.advanceTimersByTime(5000);
    expect(api.getFocusCommsStatus).not.toHaveBeenCalled();
  });

  it('polls comms on flag, updates status, toasts and stops on done', async () => {
    api.getFocusCommsStatus.mockResolvedValue({ status: 'done', sent: 3, total: 3, failed: 0 });
    const addToast = vi.fn();
    const { result } = renderHook(() => useFocusPolling(addToast));
    act(() => { result.current.setFocusCommsPolling(true); });
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    expect(api.getFocusCommsStatus).toHaveBeenCalled();
    expect(result.current.focusCommsStatus.status).toBe('done');
    expect(result.current.focusCommsPolling).toBe(false);
    expect(addToast).toHaveBeenCalled();
  });

  it('polls comments on flag, updates status, toasts and stops on done', async () => {
    api.getFocusCommentsStatus.mockResolvedValue({ status: 'done', entered: 5, skipped: 1, failed: 0 });
    const addToast = vi.fn();
    const { result } = renderHook(() => useFocusPolling(addToast));
    act(() => { result.current.setFocusCommentsPolling(true); });
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    expect(api.getFocusCommentsStatus).toHaveBeenCalled();
    expect(result.current.focusCommentsStatus.status).toBe('done');
    expect(result.current.focusCommentsPolling).toBe(false);
    expect(addToast).toHaveBeenCalled();
  });
});

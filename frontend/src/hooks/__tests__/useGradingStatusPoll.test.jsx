import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../services/api', () => ({ getStatus: vi.fn() }));

import * as api from '../../services/api';
import { useGradingStatusPoll } from '../useGradingStatusPoll';

// Characterization net for the App.jsx -> useGradingStatusPoll extraction (slice 6).
// Pins the load-bearing poll behaviors: no poll when idle, polls + setStatus when
// running, exponential backoff when the server is idle, stop when grading finishes,
// and cleanup-on-unmount (no poll after teardown).
const RUNNING = { is_running: true, log: [], results: [], progress: 0 };

describe('useGradingStatusPoll', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    api.getStatus.mockResolvedValue({ ...RUNNING });
  });
  afterEach(() => { vi.useRealTimers(); });

  it('does not poll when grading is not running', async () => {
    renderHook(() => useGradingStatusPoll({ status: { is_running: false }, setStatus: vi.fn() }));
    await vi.advanceTimersByTimeAsync(5000);
    expect(api.getStatus).not.toHaveBeenCalled();
  });

  it('polls after 500ms and forwards the response to setStatus', async () => {
    const setStatus = vi.fn();
    renderHook(() => useGradingStatusPoll({ status: { ...RUNNING }, setStatus }));
    expect(api.getStatus).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(500);
    expect(api.getStatus).toHaveBeenCalledTimes(1);
    expect(setStatus).toHaveBeenCalledWith({ ...RUNNING });
  });

  it('backs off to 1000ms after an idle tick (no activity)', async () => {
    renderHook(() => useGradingStatusPoll({ status: { ...RUNNING }, setStatus: vi.fn() }));
    await vi.advanceTimersByTimeAsync(500);
    expect(api.getStatus).toHaveBeenCalledTimes(1); // first tick at 500
    await vi.advanceTimersByTimeAsync(999);
    expect(api.getStatus).toHaveBeenCalledTimes(1); // not yet — next is at +1000
    await vi.advanceTimersByTimeAsync(1);
    expect(api.getStatus).toHaveBeenCalledTimes(2); // second tick at 1500
  });

  it('stops scheduling once the server reports grading finished', async () => {
    api.getStatus.mockResolvedValue({ is_running: false });
    renderHook(() => useGradingStatusPoll({ status: { ...RUNNING }, setStatus: vi.fn() }));
    await vi.advanceTimersByTimeAsync(500);
    expect(api.getStatus).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(20000);
    expect(api.getStatus).toHaveBeenCalledTimes(1); // no further polls after is_running=false
  });

  it('cancels the poll on unmount (no request after teardown)', async () => {
    const { unmount } = renderHook(() => useGradingStatusPoll({ status: { ...RUNNING }, setStatus: vi.fn() }));
    unmount();
    await vi.advanceTimersByTimeAsync(5000);
    expect(api.getStatus).not.toHaveBeenCalled();
  });
});

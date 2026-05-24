import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as api from '../../services/api';
import { useOutlookSendPolling } from '../useOutlookSendPolling';

vi.mock('../../services/api', () => ({
  getOutlookSendStatus: vi.fn(),
  markConfirmationsSent: vi.fn(() => Promise.resolve()),
  markFileConfirmationsSent: vi.fn(() => Promise.resolve()),
}));

const makeInputs = (over = {}) => ({
  addToast: vi.fn(),
  pendingConfirmationIds: { current: [] },
  pendingConfirmationFilenames: { current: [] },
  setPendingConfirmations: vi.fn(),
  fetchPendingConfirmations: vi.fn(),
  ...over,
});

describe('useOutlookSendPolling', () => {
  beforeEach(() => { vi.useFakeTimers(); Object.values(api).forEach((f) => f.mockClear?.()); });
  afterEach(() => { vi.useRealTimers(); });

  it('starts idle, not polling, exposes the setter bundle', () => {
    const { result } = renderHook(() => useOutlookSendPolling(makeInputs()));
    expect(result.current.outlookSendStatus.status).toBe('idle');
    expect(result.current.outlookSendPolling).toBe(false);
    expect(typeof result.current.setOutlookSendPolling).toBe('function');
  });

  it('does not poll while the flag is false', () => {
    renderHook(() => useOutlookSendPolling(makeInputs()));
    vi.advanceTimersByTime(5000);
    expect(api.getOutlookSendStatus).not.toHaveBeenCalled();
  });

  it('polls on flag, updates status, toasts and stops on done', async () => {
    api.getOutlookSendStatus.mockResolvedValue({ status: 'done', sent: 2, total: 2, failed: 0 });
    const inputs = makeInputs();
    const { result } = renderHook(() => useOutlookSendPolling(inputs));
    act(() => { result.current.setOutlookSendPolling(true); });
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    expect(api.getOutlookSendStatus).toHaveBeenCalled();
    expect(result.current.outlookSendStatus.status).toBe('done');
    expect(result.current.outlookSendPolling).toBe(false);
    expect(inputs.addToast).toHaveBeenCalled();
  });

  it('marks pending portal confirmations sent on done', async () => {
    api.getOutlookSendStatus.mockResolvedValue({ status: 'done', sent: 1, total: 1, failed: 0 });
    const inputs = makeInputs({ pendingConfirmationIds: { current: [10, 11] } });
    const { result } = renderHook(() => useOutlookSendPolling(inputs));
    act(() => { result.current.setOutlookSendPolling(true); });
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    expect(api.markConfirmationsSent).toHaveBeenCalledWith([10, 11], 'sent');
    expect(inputs.setPendingConfirmations).toHaveBeenCalledWith(0);
    expect(inputs.pendingConfirmationIds.current).toEqual([]);
  });

  it('marks file-based confirmations sent and refreshes the count on done', async () => {
    api.getOutlookSendStatus.mockResolvedValue({ status: 'done', sent: 1, total: 1, failed: 0 });
    const inputs = makeInputs({ pendingConfirmationFilenames: { current: ['a.docx', 'b.docx'] } });
    const { result } = renderHook(() => useOutlookSendPolling(inputs));
    act(() => { result.current.setOutlookSendPolling(true); });
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    expect(api.markFileConfirmationsSent).toHaveBeenCalledWith(['a.docx', 'b.docx']);
    expect(inputs.fetchPendingConfirmations).toHaveBeenCalledTimes(1);
    expect(inputs.pendingConfirmationFilenames.current).toEqual([]);
  });
});

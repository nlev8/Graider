import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as api from '../../services/api';
import { usePortalSubmissions } from '../usePortalSubmissions';

vi.mock('../../services/api', () => ({ getPortalSubmissions: vi.fn() }));

const props = (over = {}) => ({ user: { id: 'u1' }, showTutorial: false, userApproved: true, setPendingConfirmations: vi.fn(), ...over });

describe('usePortalSubmissions', () => {
  beforeEach(() => { vi.useFakeTimers(); api.getPortalSubmissions.mockReset(); api.getPortalSubmissions.mockResolvedValue({ submissions: [{ id: 1 }], pending_confirmations: 2 }); });
  afterEach(() => { vi.useRealTimers(); });

  it('does not fetch without an approved teacher session', () => {
    renderHook(() => usePortalSubmissions(props({ userApproved: null })));
    renderHook(() => usePortalSubmissions(props({ user: null })));
    renderHook(() => usePortalSubmissions(props({ showTutorial: true })));
    vi.advanceTimersByTime(1000);
    expect(api.getPortalSubmissions).not.toHaveBeenCalled();
  });

  it('fetches on mount, sets submissions + pending count', async () => {
    const inputs = props();
    const { result } = renderHook(() => usePortalSubmissions(inputs));
    await act(async () => { await Promise.resolve(); });
    expect(api.getPortalSubmissions).toHaveBeenCalledTimes(1);
    expect(result.current.portalSubmissions).toEqual([{ id: 1 }]);
    expect(inputs.setPendingConfirmations).toHaveBeenCalledWith(2);
  });

  it('polls every 30s', async () => {
    const { unmount } = renderHook(() => usePortalSubmissions(props()));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); }); // flush initial fetch
    const before = api.getPortalSubmissions.mock.calls.length;
    expect(before).toBeGreaterThanOrEqual(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(api.getPortalSubmissions.mock.calls.length).toBe(before + 1); // one more poll after 30s
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(api.getPortalSubmissions.mock.calls.length).toBe(before + 2); // repeating interval, not one-shot
    unmount();
  });

  it('returns the current portalSubmissions value', () => {
    const { result } = renderHook(() => usePortalSubmissions(props({ userApproved: null })));
    expect(result.current.portalSubmissions).toEqual([]);
  });
});

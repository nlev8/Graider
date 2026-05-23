import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '../../services/api';
import { useSubscription } from '../useSubscription';

vi.mock('../../services/api', () => ({ getSubscriptionStatus: vi.fn() }));

describe('useSubscription', () => {
  beforeEach(() => { api.getSubscriptionStatus.mockReset(); api.getSubscriptionStatus.mockResolvedValue({ plan: 'pro' }); });

  it('does not fetch unless the billing tab is selected', () => {
    const { result } = renderHook(({ tab }) => useSubscription(tab), { initialProps: { tab: 'general' } });
    expect(api.getSubscriptionStatus).not.toHaveBeenCalled();
    expect(result.current.subscription).toBe(null);
    expect(result.current.subscriptionLoading).toBe(false);
  });

  it('loads subscription when billing tab is selected (once-ever per selection)', async () => {
    const { result, rerender } = renderHook(({ tab }) => useSubscription(tab), { initialProps: { tab: 'general' } });
    rerender({ tab: 'billing' });
    await waitFor(() => expect(result.current.subscription).toEqual({ plan: 'pro' }));
    expect(api.getSubscriptionStatus).toHaveBeenCalledTimes(1);
    expect(result.current.subscriptionLoading).toBe(false);
  });

  it('exposes setters for the forwarded bundle', () => {
    const { result } = renderHook(() => useSubscription('general'));
    expect(typeof result.current.setSubscription).toBe('function');
    expect(typeof result.current.setSubscriptionLoading).toBe('function');
  });

  it('keeps subscription null on an error response and settles loading (the !res.error guard)', async () => {
    api.getSubscriptionStatus.mockResolvedValue({ error: 'boom' });
    const { result, rerender } = renderHook(({ tab }) => useSubscription(tab), { initialProps: { tab: 'general' } });
    rerender({ tab: 'billing' });
    await waitFor(() => expect(result.current.subscriptionLoading).toBe(false));
    expect(result.current.subscription).toBe(null);
  });

  it('swallows a rejected fetch and settles loading (the .catch)', async () => {
    api.getSubscriptionStatus.mockRejectedValue(new Error('network'));
    const { result, rerender } = renderHook(({ tab }) => useSubscription(tab), { initialProps: { tab: 'general' } });
    rerender({ tab: 'billing' });
    await waitFor(() => expect(result.current.subscriptionLoading).toBe(false));
    expect(result.current.subscription).toBe(null);
  });
});

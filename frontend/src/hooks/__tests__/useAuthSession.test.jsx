import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock the external boundaries the auth lifecycle touches, BEFORE importing the hook.
vi.mock('../../services/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signOut: vi.fn().mockResolvedValue({}),
    },
  },
}));
vi.mock('../../services/posthog', () => ({
  initPostHog: vi.fn(),
  identifyUser: vi.fn(),
  resetUser: vi.fn(),
}));

import { supabase } from '../../services/supabase';
import { initPostHog, resetUser } from '../../services/posthog';
import { useAuthSession } from '../useAuthSession';

// Characterization net for the App.jsx -> useAuthSession extraction (slice 3).
// Pins the load-bearing auth behaviors the verbatim move must preserve: the
// localhost dev-user bootstrap, the approval gate, handleLogout's teardown, the
// recovery-hash -> showPasswordReset init, and the non-localhost session bootstrap
// (getSession + onAuthStateChange subscribe + unsubscribe on cleanup).
describe('useAuthSession', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    supabase.auth.getSession.mockResolvedValue({ data: { session: null } });
    supabase.auth.onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } });
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) }));
    window.__graiderUser = undefined;
    window.history.replaceState({}, '', '/');
    window.location.hash = '';
    localStorage.clear();
  });
  afterEach(() => { window.location.hash = ''; });

  it('localhost: bootstraps the dev user, clears loading, and auto-approves', async () => {
    const { result } = renderHook(() => useAuthSession(true));
    await waitFor(() => expect(result.current.authLoading).toBe(false));
    expect(result.current.user).toEqual({ id: 'local-dev', email: 'dev@localhost' });
    await waitFor(() => expect(result.current.userApproved).toBe(true));
    // localhost skips analytics init
    expect(initPostHog).not.toHaveBeenCalled();
  });

  it('handleLogout tears down: clears SSO sessions, resets analytics, signs out, clears user', async () => {
    const { result } = renderHook(() => useAuthSession(true));
    await waitFor(() => expect(result.current.user).not.toBeNull());

    await act(async () => { await result.current.handleLogout(); });

    // both SSO logout endpoints hit
    const urls = global.fetch.mock.calls.map((c) => c[0]);
    expect(urls).toContain('/api/clever/logout');
    expect(urls).toContain('/api/classlink/logout');
    expect(resetUser).toHaveBeenCalled();
    expect(supabase.auth.signOut).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
    expect(window.__graiderUser).toBeNull();
  });

  it('initializes showPasswordReset from a recovery hash', () => {
    window.location.hash = '#type=recovery&token=abc';
    const { result } = renderHook(() => useAuthSession(true));
    expect(result.current.showPasswordReset).toBe(true);
  });

  it('non-localhost: reads the Supabase session and subscribes to auth changes (with cleanup)', async () => {
    const unsubscribe = vi.fn();
    supabase.auth.onAuthStateChange.mockReturnValue({ data: { subscription: { unsubscribe } } });
    const { result, unmount } = renderHook(() => useAuthSession(false));
    await waitFor(() => expect(result.current.authLoading).toBe(false));
    expect(supabase.auth.getSession).toHaveBeenCalled();
    expect(supabase.auth.onAuthStateChange).toHaveBeenCalled();
    expect(initPostHog).toHaveBeenCalled(); // analytics init runs off-localhost
    unmount();
    expect(unsubscribe).toHaveBeenCalled();
  });
});

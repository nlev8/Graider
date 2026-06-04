import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Render-time smoke test for the App shell. The codebase previously had NO test that
// mounts <App/> (App.logout/AppTabImports are static source checks; smoke avoids App),
// so a render-time crash — e.g. the temporal-dead-zone use-before-define a decomposition
// slice can introduce by calling a factory hook with a const defined later — would pass
// build + unit tests + CI and white-screen users. This test mounts the real App shell so
// any such render-time ReferenceError fails fast. (Caught the slice-15 useMarkerEditing TDZ.)
vi.mock('../services/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signOut: vi.fn().mockResolvedValue({}),
    },
  },
}));
vi.mock('../services/posthog', () => ({
  initPostHog: vi.fn(), identifyUser: vi.fn(), resetUser: vi.fn(), track: vi.fn(),
}));

describe('App mounts without crashing (render-time smoke)', () => {
  beforeEach(() => {
    global.fetch = vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) }));
    localStorage.clear();
    window.history.replaceState({}, '', '/');
    // jsdom does not implement these layout APIs that child components call on mount.
    Element.prototype.scrollIntoView = vi.fn();
    window.scrollTo = vi.fn();
  });
  afterEach(() => { vi.clearAllMocks(); });

  // Mounting the full App shell is heavy (~3s); give it headroom under full-suite load.
  it('renders the logged-out shell without throwing (guards against use-before-define)', { timeout: 20000 }, async () => {
    vi.useRealTimers(); // defend against fake timers leaking from another file
    const App = (await import('../App')).default;
    let result;
    expect(() => { result = render(<App />); }).not.toThrow();
    result?.unmount(); // stop the App's effects so the worker doesn't hang
  });
});

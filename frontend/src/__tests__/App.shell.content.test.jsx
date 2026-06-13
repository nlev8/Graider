import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * Content-asserting App shell mount test — the pre-split safety net for the
 * App.jsx finale decomposition (CQ campaign, "no function >300 LOC").
 *
 * App.mount.test.jsx only asserts that render() doesn't throw. This test goes
 * further: it mounts the LOGGED-IN shell (jsdom hostname is "localhost", so
 * useAuthSession auto-logs-in as local-dev and auto-approves) and asserts the
 * load-bearing shell content survives:
 *   - the header toolbar ("Start Grading" button + data-tutorial="grade-toolbar")
 *   - the always-mounted Assistant container (data-tutorial="assistant-chat")
 *   - every sidebar tab label from the TABS config
 *   - the theme toggle
 *
 * Wave-6/8/9 precedent: this test must be green BEFORE the split (commit 1)
 * and stay green after, proving the extracted sections render identical
 * shell content.
 */
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

// Full empty-but-shape-correct grading status. /api/status MUST return this
// shape: App stores the response verbatim via setStatus(), and several App
// effects read status.results.length — a bare {} would crash post-mount.
const EMPTY_STATUS = {
  is_running: false, progress: 0, total: 0, current_file: '',
  log: [], results: [], complete: false, error: null,
};

describe('App shell content (logged-in, pre/post-split contract)', () => {
  beforeEach(() => {
    global.fetch = vi.fn((url) => {
      const path = String(url);
      const body = path.includes('/api/status') ? EMPTY_STATUS : {};
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
    });
    localStorage.clear();
    // Mark tutorial complete so the onboarding flow doesn't start the tutorial overlay.
    localStorage.setItem('graider-tutorial-complete', 'true');
    window.history.replaceState({}, '', '/');
    Element.prototype.scrollIntoView = vi.fn();
    window.scrollTo = vi.fn();
  });
  afterEach(() => { vi.clearAllMocks(); });

  it('renders header toolbar, sidebar nav, and shell tutorial anchors', { timeout: 30000 }, async () => {
    vi.useRealTimers();
    const App = (await import('../App')).default;
    const { container, unmount } = render(<App />);

    // Header toolbar (always rendered when logged in + approved).
    // findAll — the always-mounted GradeTab renders its own Start Grading control.
    const startButtons = await screen.findAllByText('Start Grading', {}, { timeout: 15000 });
    expect(startButtons.length).toBeGreaterThan(0);

    // Shell-owned data-tutorial anchors (TutorialOverlay targets — must survive verbatim)
    expect(container.querySelector('[data-tutorial="grade-toolbar"]')).not.toBeNull();
    expect(container.querySelector('[data-tutorial="assistant-chat"]')).not.toBeNull();

    // Sidebar nav renders every tab label from the TABS config
    for (const label of [
      'Grade', 'Results', 'Grading Setup', 'Analytics', 'Planner',
      'Script Builder', 'Assistant', 'Settings', 'Help',
    ]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }

    // Theme toggle in the header bar
    expect(screen.getByTitle(/Switch to (Light|Dark) Mode/)).toBeTruthy();

    unmount();
  });
});

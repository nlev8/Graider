import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import OnboardingWizard from '../components/OnboardingWizard';

// Mock api.js (getAuthHeaders used inside the wizard)
vi.mock('../services/api', () => ({
  getAuthHeaders: vi.fn().mockResolvedValue({}),
}));

// Icon renders nothing real in tests — avoid lucide-react render issues
vi.mock('../components/Icon', () => ({
  default: ({ name }) => React.createElement('span', { 'data-icon': name }),
}));

// rubricPresets returns something safe
vi.mock('../data/rubricPresets', () => ({
  RUBRIC_PRESETS: {
    default: { name: 'Default', description: '', categories: [] },
  },
  getPresetForStateSubject: () => ({
    name: 'FL US History',
    description: '',
    categories: [],
    badge: null,
  }),
}));

const BASE_PROPS = {
  config: {
    teacher_name: 'Test Teacher',
    teacher_email: 'test@school.edu',
    school_name: 'Test School',
    grade_level: '7',
    subject: 'US History',
    state: 'FL',
    grading_period: 'Q1',
  },
  setConfig: vi.fn(),
  rubric: { gradingStyle: 'standard', categories: [] },
  setRubric: vi.fn(),
  apiKeys: { openaiConfigured: true, anthropicConfigured: false, geminiConfigured: false },
  setApiKeys: vi.fn(),
  onComplete: vi.fn(),
  addToast: vi.fn(),
  theme: 'light',
  toggleTheme: vi.fn(),
};

/**
 * Advance through the wizard by clicking the primary nav button n times.
 * The primary button is the last <button class="btn btn-primary"> in the footer.
 * Requires that canContinue() is satisfied at each step (step 1 is gated by teacher name,
 * which BASE_PROPS.config.teacher_name satisfies).
 */
function clickNext(container, times = 1) {
  for (let i = 0; i < times; i++) {
    const btns = container.querySelectorAll('button.btn.btn-primary');
    const btn = btns[btns.length - 1]; // last btn-primary is always the footer Next/Continue
    fireEvent.click(btn);
  }
}

describe('OnboardingWizard — SSO detection via auth_source', () => {
  let savedGraiderUser;

  beforeEach(() => {
    savedGraiderUser = window.__graiderUser;
  });

  afterEach(() => {
    window.__graiderUser = savedGraiderUser;
  });

  it('ClassLink teacher with UUID id + auth_source shows "Your Roster is Ready" at step 6', () => {
    // Simulate a post-branch ClassLink session: real UUID, auth_source set on window global.
    // The user prop intentionally has NO auth_source (mirrors _setUser in App.jsx which
    // only copies id/email/user_metadata but not auth_source).
    window.__graiderUser = {
      id: 'a1b2c3d4-0000-0000-0000-000000000001',
      email: 'teacher@classlink.edu',
      name: 'Test Teacher',
      auth_source: 'classlink',
    };

    const user = { id: 'a1b2c3d4-0000-0000-0000-000000000001', email: 'teacher@classlink.edu' };

    const { getByText, container } = render(<OnboardingWizard {...BASE_PROPS} user={user} />);

    // Step 0 → 5 (6 clicks)
    clickNext(container, 6); // 0→1→2→3→4→5→6

    // Step 6 — SSO branch: should show the "Your Roster is Ready" heading
    expect(getByText('Your Roster is Ready')).toBeTruthy();
  });

  it('ClassLink teacher with auth_source shows "ClassLink (auto-sync)" on the summary (step 7)', () => {
    window.__graiderUser = {
      id: 'a1b2c3d4-0000-0000-0000-000000000002',
      email: 'teacher2@classlink.edu',
      name: 'Test Teacher',
      auth_source: 'classlink',
    };

    const user = { id: 'a1b2c3d4-0000-0000-0000-000000000002', email: 'teacher2@classlink.edu' };

    const { getByText, container } = render(<OnboardingWizard {...BASE_PROPS} user={user} />);

    clickNext(container, 7); // 0→1→2→3→4→5→6→7

    // Step 7 summary must show ClassLink auto-sync, not "Manual upload"
    expect(getByText('ClassLink (auto-sync)')).toBeTruthy();
  });

  it('non-SSO teacher with plain UUID id shows "Manual upload" on the summary (regression guard)', () => {
    // No auth_source on window global, no prefix on id — regular Supabase user
    window.__graiderUser = {
      id: 'b9e8d7c6-0000-0000-0000-000000000003',
      email: 'teacher3@school.edu',
    };

    const user = { id: 'b9e8d7c6-0000-0000-0000-000000000003', email: 'teacher3@school.edu' };

    const { getByText, container } = render(<OnboardingWizard {...BASE_PROPS} user={user} />);

    clickNext(container, 7); // 0→1→2→3→4→5→6→7

    expect(getByText('Manual upload')).toBeTruthy();
  });
});

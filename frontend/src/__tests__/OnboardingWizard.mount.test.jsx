import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import OnboardingWizard from '../components/OnboardingWizard';

// Render-time smoke test for OnboardingWizard. Added with the CQ wave-3 split of
// OnboardingWizard.jsx into components/onboarding-wizard/* (mirrors
// GradeTab.mount.test.jsx / AnalyticsTab.mount.test.jsx from waves 1-2, added for
// the same reason): build + unit tests pass even if a split leaves an unimported
// component or mis-threaded prop that white-screens a step at runtime. This walks
// the real wizard through every step so each extracted step component
// (WelcomeStep, AboutYouStep, ClassroomStep, GradingStyleStep, RubricSetupStep,
// AiConnectionStep, RosterStep, AllSetStep, WizardProgressHeader) actually
// renders content, and verifies state threading survives navigation (the wizard
// caution: per-step state must live in the always-mounted shell, not in the
// conditionally-rendered steps).
vi.mock('../services/api', () => ({
  getAuthHeaders: vi.fn().mockResolvedValue({}),
}));

vi.mock('../components/Icon', () => ({
  default: ({ name }) => React.createElement('span', { 'data-icon': name }),
}));

vi.mock('../data/rubricPresets', () => ({
  RUBRIC_PRESETS: {
    default: { name: 'Standard Rubric', description: '', categories: [{ name: 'Accuracy', weight: 100 }] },
  },
  getPresetForStateSubject: () => ({
    name: 'FL B.E.S.T. US History',
    description: '',
    categories: [{ name: 'Content', weight: 60 }, { name: 'Effort', weight: 40 }],
    badge: 'B.E.S.T.',
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
  user: { id: 'b9e8d7c6-0000-0000-0000-000000000099', email: 'teacher@school.edu' },
};

/** Click the footer primary button (always the last .btn.btn-primary). */
function clickNext(container, times = 1) {
  for (let i = 0; i < times; i++) {
    const btns = container.querySelectorAll('button.btn.btn-primary');
    fireEvent.click(btns[btns.length - 1]);
  }
}

describe('OnboardingWizard mounts and renders every extracted step (render-time smoke)', () => {
  let savedGraiderUser;

  beforeEach(() => {
    savedGraiderUser = window.__graiderUser;
    window.__graiderUser = undefined;
  });

  afterEach(() => {
    window.__graiderUser = savedGraiderUser;
    vi.clearAllMocks();
  });

  it('walks all 8 steps and asserts real content from each extracted component', () => {
    const { getByText, getByPlaceholderText, container } = render(<OnboardingWizard {...BASE_PROPS} />);

    // WizardProgressHeader (chrome, always mounted)
    expect(getByText('Step 1 of 8')).toBeTruthy();

    // Step 0 — WelcomeStep (non-Clever user sees the AI Services Notice)
    expect(getByText('Welcome to Graider!')).toBeTruthy();
    expect(getByText('AI Services Notice')).toBeTruthy();
    expect(getByText("Let's Get Started")).toBeTruthy();

    // Step 1 — AboutYouStep (prefilled from config via shell state)
    clickNext(container);
    expect(getByText('About You')).toBeTruthy();
    expect(getByPlaceholderText('e.g. Ms. Johnson').value).toBe('Test Teacher');

    // Step 2 — ClassroomStep (selects threaded from shell wizardData)
    clickNext(container);
    expect(getByText('Your Classroom')).toBeTruthy();
    expect(getByText('Florida')).toBeTruthy();

    // Step 3 — GradingStyleStep (GRADING_STYLES from constants.js)
    clickNext(container);
    expect(getByText('Grading Style')).toBeTruthy();
    expect(getByText('Lenient')).toBeTruthy();
    expect(getByText('Strict')).toBeTruthy();

    // Step 4 — RubricSetupStep (FL shows the matched B.E.S.T. preset card)
    clickNext(container);
    expect(getByText('Rubric Setup')).toBeTruthy();
    expect(getByText('FL B.E.S.T. US History')).toBeTruthy();
    expect(getByText('Customize Later')).toBeTruthy();

    // Step 5 — AiConnectionStep (key already configured via apiKeys prop)
    clickNext(container);
    expect(getByText('AI Connection')).toBeTruthy();
    expect(getByText('OpenAI API Key (Recommended)')).toBeTruthy();

    // Step 6 — RosterStep (non-SSO branch: manual CSV upload)
    clickNext(container);
    expect(getByText('Import Your Class Roster')).toBeTruthy();
    expect(getByText('Example CSV format')).toBeTruthy();

    // Step 7 — AllSetStep (summary reads shell state)
    clickNext(container);
    expect(getByText("You're All Set!")).toBeTruthy();
    expect(getByText('Manual upload')).toBeTruthy();
    expect(getByText('Create Your First Assignment')).toBeTruthy();
    expect(getByText('Step 8 of 8')).toBeTruthy();
  });

  it('threads step state through navigation: edits in AboutYouStep survive Back/Next round-trips', () => {
    const { getByText, getByPlaceholderText, container } = render(<OnboardingWizard {...BASE_PROPS} />);

    // Go to step 1 and change the teacher name (state lives in the shell)
    clickNext(container);
    const nameInput = getByPlaceholderText('e.g. Ms. Johnson');
    fireEvent.change(nameInput, { target: { value: 'Ms. Rivera' } });
    expect(nameInput.value).toBe('Ms. Rivera');

    // Navigate forward to step 2, then back to step 1 — the step component
    // unmounted and remounted, but the edit must persist (shell-held state).
    clickNext(container);
    expect(getByText('Your Classroom')).toBeTruthy();
    fireEvent.click(getByText('Back'));
    expect(getByPlaceholderText('e.g. Ms. Johnson').value).toBe('Ms. Rivera');

    // And the summary step reflects the edited value end-to-end
    clickNext(container, 6); // 1→2→3→4→5→6→7
    expect(getByText("You're All Set!")).toBeTruthy();
    expect(getByText('Ms. Rivera')).toBeTruthy();
  });
});

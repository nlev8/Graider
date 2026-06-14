import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

// Render-time smoke test for CleverSyncSection. Added with the CQ wave-8
// split (#cq8-06) that extracted CleverAccommSuggestionsPanel from the parent.
// Verifies: (1) renders nothing when not a Clever user, (2) renders section
// header when isCleverUser=true, (3) "Connected" badge appears, (4) sync button
// present, (5) accommodation panel not shown when no suggestions, (6) accommodation
// panel shown when suggestions provided. Tests use Vitest native matchers
// (toBeTruthy), not jest-dom.

vi.mock('../services/api', () => ({
  listPeriods: vi.fn().mockResolvedValue({ periods: [] }),
  getStudentAccommodations: vi.fn().mockResolvedValue({ accommodations: {} }),
  getAuthHeaders: vi.fn().mockResolvedValue({}),
}));

import CleverSyncSection from '../components/settings-classroom/CleverSyncSection';

afterEach(() => {
  vi.clearAllMocks();
});

function baseProps(overrides = {}) {
  return {
    addToast: vi.fn(),
    cleverAccommSuggestions: null,
    cleverApplying: false,
    cleverSelectedSections: {},
    cleverSyncResult: null,
    cleverSyncing: false,
    isCleverUser: true,
    setCleverAccommSuggestions: vi.fn(),
    setCleverApplying: vi.fn(),
    setCleverSelectedSections: vi.fn(),
    setCleverSyncResult: vi.fn(),
    setCleverSyncing: vi.fn(),
    setPeriods: vi.fn(),
    setStudentAccommodations: vi.fn(),
    ...overrides,
  };
}

describe('CleverSyncSection mounts without crashing (render-time smoke)', () => {
  it('renders nothing when isCleverUser=false', () => {
    const { container } = render(
      <CleverSyncSection {...baseProps({ isCleverUser: false })} />
    );
    expect(container.firstChild).toBeFalsy();
  });

  it('renders "Clever Roster Sync" heading when isCleverUser=true', () => {
    render(<CleverSyncSection {...baseProps()} />);
    expect(screen.getByText('Clever Roster Sync')).toBeTruthy();
  });

  it('renders "Connected" badge', () => {
    render(<CleverSyncSection {...baseProps()} />);
    expect(screen.getByText('Connected')).toBeTruthy();
  });

  it('renders "Sync from Clever" button', () => {
    render(<CleverSyncSection {...baseProps()} />);
    expect(screen.getByText('Sync from Clever')).toBeTruthy();
  });

  it('does not render accommodation panel when cleverAccommSuggestions is null', () => {
    render(<CleverSyncSection {...baseProps({ cleverAccommSuggestions: null })} />);
    expect(screen.queryByText('IEP/ELL Accommodation Suggestions')).toBeFalsy();
  });

  it('renders accommodation panel when cleverAccommSuggestions has entries', () => {
    const suggestions = {
      'stu-1': {
        name: 'Alice Smith',
        iep_status: true,
        ell_status: false,
        home_language: 'English',
        suggested_presets: ['extended_time'],
      },
    };
    render(
      <CleverSyncSection
        {...baseProps({ cleverAccommSuggestions: suggestions })}
      />
    );
    expect(screen.getByText('IEP/ELL Accommodation Suggestions')).toBeTruthy();
    expect(screen.getByText('Alice Smith')).toBeTruthy();
    expect(screen.getByText('Apply All Accommodations')).toBeTruthy();
  });
});

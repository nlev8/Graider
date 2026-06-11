import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SettingsPrivacy from '../components/SettingsPrivacy';

// Content-asserting mount test for SettingsPrivacy. Added with the CQ wave-4
// split of SettingsPrivacy.jsx into settings-privacy/* (mirrors
// AssistantChat.mount.test.jsx from wave 3, for the same reason): before this
// test, the only renderer was the no-crash smoke in SettingsPrivacy.test.jsx,
// which passes even if a split leaves an unimported section component or a
// mis-threaded prop that blanks part of the panel at runtime. This test
// asserts real content from every extracted section actually mounts.

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

const base = () => ({
  config: { subject: 'Math', grade_level: '8' },
  periods: [],
  studentHistoryList: [],
  studentHistoryLoading: false,
  selectedStudentHistory: null,
  exportStudentSearch: { active: false, query: '', results: [], allStudents: [] },
  importStudentData: { active: false, preview: null, file: null, importing: false, selectedPeriod: '' },
  importFileRef: { current: null },
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('SettingsPrivacy mounts with content from every extracted section', () => {
  it('renders header, features grid, data management, profiles, and trusted writers', () => {
    render(<SettingsPrivacy {...makeProps()} />);

    // Orchestrator header
    expect(screen.getByText('Privacy & Data (FERPA)')).toBeTruthy();
    // PrivacyFeaturesSection — all four feature cards
    expect(screen.getByText('PII Sanitization')).toBeTruthy();
    expect(screen.getByText('No Third-Party Sharing')).toBeTruthy();
    expect(screen.getByText('No AI Training')).toBeTruthy();
    expect(screen.getByText('Audit Logging')).toBeTruthy();
    // DataManagementSection — all five actions, including the nested
    // Export/Import student-data controls
    expect(screen.getByText('Data Management')).toBeTruthy();
    expect(screen.getByText('View Data Summary')).toBeTruthy();
    expect(screen.getByText('Export All Data')).toBeTruthy();
    expect(screen.getByText('Export Student Data')).toBeTruthy();
    expect(screen.getByText('Import Student Data')).toBeTruthy();
    expect(screen.getByText('Delete All Data')).toBeTruthy();
    // WritingProfilesSection — header + empty-state hint
    expect(screen.getByText('Student Writing Profiles')).toBeTruthy();
    expect(screen.getByText('Click "Refresh" to load student writing profiles')).toBeTruthy();
    // TrustedWritersSection — header + empty state
    expect(screen.getByText('Trusted Writers')).toBeTruthy();
    expect(screen.getByText(/No trusted writers yet/)).toBeTruthy();
    // StudentHistoryModal — early-returns null when no profile is selected
    expect(screen.queryByText('Student Profile')).toBeNull();
  });

  it('renders populated profile rows, trusted-writer chips, and the history modal', () => {
    render(
      <SettingsPrivacy
        {...makeProps({
          config: { subject: 'Math', grade_level: '8', trustedStudents: ['sid-42'] },
          studentHistoryList: [
            { student_id: 's1', name: 'Alice Smith', submissions_analyzed: 3, avg_complexity: 7.2 },
          ],
          selectedStudentHistory: { name: 'Alice Smith', student_id: 's1', avg_complexity: 7.2 },
        })}
      />
    );

    // WritingProfilesSection populated branch — row + bulk delete button
    expect(screen.getAllByText('Alice Smith').length).toBeGreaterThan(0);
    expect(screen.getByText(/3 submissions/)).toBeTruthy();
    expect(screen.getByText('Delete All Profiles')).toBeTruthy();
    // TrustedWritersSection populated branch — chip falls back to the raw id
    // when no result/period match exists, plus the Clear All button
    expect(screen.getByText('sid-42')).toBeTruthy();
    expect(screen.getByText('Clear All')).toBeTruthy();
    // StudentHistoryModal open — renders the profile JSON dump
    expect(screen.getByText(/"avg_complexity": 7.2/)).toBeTruthy();
  });
});

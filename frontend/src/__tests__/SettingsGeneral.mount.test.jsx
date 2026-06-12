import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SettingsGeneral from '../components/SettingsGeneral';

// Content-asserting mount test for SettingsGeneral. Added with the CQ wave-8
// split of SettingsGeneral.jsx into settings-general/* (mirrors
// SettingsPrivacy.mount.test.jsx from wave 4, for the same reason): before
// this test, the only renderer was the no-crash smoke in
// SettingsGeneral.test.jsx, which passes even if a split leaves an
// unimported section component or a mis-threaded prop that blanks part of
// the panel at runtime. This test asserts real content from every extracted
// section actually mounts.

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

const base = () => ({
  config: {
    teacher_name: 'Mr. Smith',
    teacher_email: 'smith@school.edu',
    school_name: 'Lincoln Middle School',
    subject: 'Math',
    grade_level: '8',
    state: 'FL',
    email_signature: '',
    showToastNotifications: true,
  },
  availableStates: [],
  adminStatus: null,
  adminClaimResult: null,
  adminClaimCode: '',
  vportalPassword: '',
  showVportalPassword: false,
  vportalConfigured: false,
  vportalSaving: false,
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('SettingsGeneral mounts with content from every extracted section', () => {
  it('renders profile, admin claim, gradebook, notifications, and setup wizard sections', () => {
    render(<SettingsGeneral {...makeProps()} />);

    // TeacherProfileSection — info grid + state/grade/subject + signature
    expect(screen.getByText('Teacher Name')).toBeTruthy();
    expect(screen.getByText('Teacher Email')).toBeTruthy();
    expect(screen.getByText('School Name')).toBeTruthy();
    expect(screen.getByText('State')).toBeTruthy();
    expect(screen.getByText('Grade Level')).toBeTruthy();
    expect(screen.getByText('Subject')).toBeTruthy();
    expect(screen.getByText('Email Signature')).toBeTruthy();
    expect(screen.getByText('Students will reply to this email')).toBeTruthy();
    expect(screen.getByDisplayValue('Mr. Smith')).toBeTruthy();
    // AdminAccessSection — non-admin claim branch
    expect(screen.getByText('Admin Access')).toBeTruthy();
    expect(screen.getByPlaceholderText('Enter invite code')).toBeTruthy();
    expect(screen.getByText('Claim Access')).toBeTruthy();
    // GradebookIntegrationSection
    expect(screen.getByText('Gradebook Integration')).toBeTruthy();
    expect(screen.getByText('Student Information System')).toBeTruthy();
    expect(screen.getByText('District Portal')).toBeTruthy();
    expect(screen.getByText('Portal Password')).toBeTruthy();
    expect(screen.getByText('Save Credentials')).toBeTruthy();
    // NotificationsSection
    expect(screen.getByText('Notifications')).toBeTruthy();
    expect(screen.getByText('Toast Notifications')).toBeTruthy();
    expect(screen.getByText('Show popup notifications when assignments are graded')).toBeTruthy();
    // SetupWizardSection
    expect(screen.getByText('Setup Wizard')).toBeTruthy();
    expect(screen.getByText('Run Setup Wizard Again')).toBeTruthy();
  });

  it('renders the admin badge and configured-credentials branches', () => {
    render(
      <SettingsGeneral
        {...makeProps({
          adminStatus: { is_admin: true, school: 'PS 118' },
          vportalConfigured: true,
        })}
      />
    );

    // AdminAccessSection admin branch — badge instead of claim form
    expect(screen.getByText('School Admin — PS 118')).toBeTruthy();
    expect(screen.queryByText('Claim Access')).toBeNull();
    // GradebookIntegrationSection configured branch
    expect(screen.getByText('Configured')).toBeTruthy();
  });
});

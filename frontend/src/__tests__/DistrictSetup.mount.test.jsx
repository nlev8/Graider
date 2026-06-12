import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// Render-time smoke test for the full authenticated DistrictSetup → ConfigForm
// path. Added with the CQ wave-5 split of ConfigForm (761 LOC) into
// components/district-setup/* (mirrors OnboardingWizard.mount.test.jsx /
// GradeTab.mount.test.jsx from earlier waves, added for the same reason):
// build + unit tests pass even if a split leaves an unimported component or a
// mis-threaded prop that white-screens a section at runtime. This mounts the
// real component tree and asserts content from every extracted section
// (SisProviderSection, AiKeysSection, SchoolAdminsSection, ConfigSummary,
// ChangePassword) actually renders, that loaded config values hydrate the
// credential inputs, and that state threading survives interaction (radio
// switch to OneRoster, Change Password toggle) — the state lives in the
// always-mounted ConfigForm, not in the section children.

vi.mock('../services/api', () => ({
  __esModule: true,
  // Auth gate: needs_setup false + a non-error config => authenticated ConfigForm
  getDistrictConfigStatus: vi.fn(async () => ({ needs_setup: false })),
  getDistrictConfig: vi.fn(async () => ({
    config: {
      sis_type: 'clever',
      clever_client_id: 'clever-client-abc123',
      clever_redirect_uri: 'https://app.graider.live/api/clever/callback',
      has_openai: true,
      has_clever_secret: true,
    },
  })),
  listAdmins: vi.fn(async () => ({
    admins: [{ user_id: 'u1', name: 'Ada Admin', school: 'Lincoln Middle School', granted_at: '2026-01-15T00:00:00Z' }],
  })),
  // Sections mounted inside ConfigForm
  listSsoAdmins: vi.fn(async () => ({ admins: [] })),
  getDistrictAnalytics: vi.fn(async () => ({
    overview: { total_teachers: 2, total_students: 50, total_assessments: 7, average_score: 91, grade_distribution: { A: 5 } },
    teachers: [],
  })),
  // Every other api export DistrictSetup.jsx + district-setup/* reference at
  // module load / render time.
  addSsoAdmin: vi.fn(async () => ({})),
  changeDistrictPassword: vi.fn(async () => ({})),
  createAdminInvite: vi.fn(async () => ({})),
  districtAuth: vi.fn(async () => ({})),
  districtLogout: vi.fn(async () => ({})),
  removeSsoAdmin: vi.fn(async () => ({})),
  revokeAdmin: vi.fn(async () => ({})),
  saveDistrictConfig: vi.fn(async () => ({})),
  searchTeachers: vi.fn(async () => ({ teachers: [] })),
  testDistrictConnection: vi.fn(async () => ({})),
}))

import * as api from '../services/api'
import DistrictSetup from '../components/DistrictSetup'

describe('DistrictSetup mount (authenticated ConfigForm path)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders every extracted section with hydrated config', async () => {
    render(<DistrictSetup />)

    // SisProviderSection — heading, radio labels, hydrated Clever client id
    // ("SIS Provider" appears twice by design: section heading + summary row)
    await waitFor(() => expect(screen.getAllByText('SIS Provider').length).toBe(2))
    expect(screen.getByLabelText('Clever')).toBeTruthy()
    expect(screen.getByLabelText('OneRoster')).toBeTruthy()
    expect(screen.getByDisplayValue('clever-client-abc123')).toBeTruthy()
    expect(screen.getByDisplayValue('https://app.graider.live/api/clever/callback')).toBeTruthy()
    expect(screen.getByText('Test Connection')).toBeTruthy()
    expect(screen.getByText('Save SIS Config')).toBeTruthy()

    // Secret fields stay write-only: saved secret renders blank + "Saved" badge
    expect(screen.getAllByPlaceholderText('Leave blank to keep current').length).toBe(2) // clever secret + openai key
    expect(screen.getAllByText('Saved').length).toBeGreaterThanOrEqual(2) // clever secret + openai

    // AiKeysSection
    expect(screen.getByText('AI API Keys')).toBeTruthy()
    expect(screen.getByText('Save Keys')).toBeTruthy()
    expect(screen.getByPlaceholderText('sk-ant-...')).toBeTruthy()

    // SchoolAdminsSection — admin row from listAdmins + invite form
    await waitFor(() => expect(screen.getByText('Ada Admin')).toBeTruthy())
    expect(screen.getByText('School Admins')).toBeTruthy()
    expect(screen.getByText('Create Admin Invite')).toBeTruthy()
    expect(screen.getByText('Generate Invite Code')).toBeTruthy()

    // Sections that stayed in DistrictSetup.jsx, mounted inside ConfigForm
    expect(screen.getByText('SSO Admin Access')).toBeTruthy()
    await waitFor(() => expect(screen.getByText('District Analytics')).toBeTruthy())

    // ConfigSummarySection — read-only rollup reflects loaded config
    expect(screen.getByText('Configuration Summary')).toBeTruthy()
    expect(screen.getByText('SIS Credentials')).toBeTruthy()
    expect(screen.getByText('Log Out')).toBeTruthy()

    expect(api.getDistrictConfig).toHaveBeenCalled()
    expect(api.listAdmins).toHaveBeenCalled()
  })

  it('threads state across sections: OneRoster switch + Change Password toggle', async () => {
    render(<DistrictSetup />)
    await waitFor(() => expect(screen.getByText('Test Connection')).toBeTruthy())

    // Radio lives in SisProviderSection; sisType state lives in ConfigForm
    fireEvent.click(screen.getByLabelText('OneRoster'))
    expect(screen.getByText('Base URL')).toBeTruthy()
    expect(screen.getByText('ClassLink')).toBeTruthy()
    expect(screen.getByText('PowerSchool')).toBeTruthy()
    // Summary (separate extracted section) reflects the same state change
    expect(screen.getAllByText('OneRoster').length).toBeGreaterThanOrEqual(2)

    // ChangePasswordSection toggle; pw state lives in ConfigForm
    fireEvent.click(screen.getByText('Change Password'))
    expect(screen.getByText('Current Password')).toBeTruthy()
    expect(screen.getByText('New Password')).toBeTruthy()
    expect(screen.getByText('Update Password')).toBeTruthy()
    fireEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText('Update Password')).toBeNull()
  })
})

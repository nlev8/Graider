import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mount smoke test for OneRosterSection and OneRosterCredentialsFields.
// Added with the CQ wave cq8-05 split of OneRosterFullForm 242→175 LOC:
// before this test NOTHING rendered these components — build + unit tests pass
// even if the split leaves a mis-threaded prop or broken import that white-screens
// the settings panel at runtime.

vi.mock('../services/api', () => ({
  saveOneRosterConfig: vi.fn().mockResolvedValue({}),
  testOneRosterConnection: vi.fn().mockResolvedValue({ success: true }),
  syncOneRosterRoster: vi.fn().mockResolvedValue({ counts: { students: 5, sections: 2, enrollments: 10 } }),
  deleteOneRosterData: vi.fn().mockResolvedValue({}),
  listPeriods: vi.fn().mockResolvedValue({ periods: [] }),
  applyOneRosterAccommodations: vi.fn().mockResolvedValue({ applied: 0, total: 0, errors: [] }),
  getStudentAccommodations: vi.fn().mockResolvedValue({ accommodations: {} }),
  saveOneRosterTeacherId: vi.fn().mockResolvedValue({}),
}));

const baseConfig = {
  base_url: 'https://sis.example.com/ims/oneroster/v1p1',
  client_id: 'test-client-id',
  client_secret: '',
  token_url: '',
  school_id: '',
  teacher_sourced_id: 'teacher-123',
};

const baseProps = {
  activeProvider: 'oneroster',
  addToast: vi.fn(),
  districtSisProvider: null,
  oneRosterConfig: baseConfig,
  oneRosterHasCredentials: false,
  oneRosterSaving: false,
  oneRosterStatus: null,
  oneRosterSyncResult: null,
  oneRosterSyncing: false,
  oneRosterTestResult: null,
  oneRosterAccommodations: null,
  oneRosterApplying: false,
  setOneRosterAccommodations: vi.fn(),
  setOneRosterConfig: vi.fn(),
  setOneRosterHasCredentials: vi.fn(),
  setOneRosterSaving: vi.fn(),
  setOneRosterStatus: vi.fn(),
  setOneRosterSyncResult: vi.fn(),
  setOneRosterSyncing: vi.fn(),
  setOneRosterTestResult: vi.fn(),
  setOneRosterApplying: vi.fn(),
  setPeriods: vi.fn(),
  setShowOneRosterSecret: vi.fn(),
  setStudentAccommodations: vi.fn(),
  setTeacherSisId: vi.fn(),
  showOneRosterSecret: false,
  teacherSisId: '',
};

describe('OneRosterSection', () => {
  it('renders the section heading when activeProvider is not clever', async () => {
    const { default: OneRosterSection } = await import('../components/settings-classroom/OneRosterSection');
    render(<OneRosterSection {...baseProps} />);
    expect(screen.getByText(/OneRoster Integration/i)).toBeTruthy();
  });

  it('renders OneRosterFullForm (with credential fields) when districtSisProvider is not oneroster', async () => {
    const { default: OneRosterSection } = await import('../components/settings-classroom/OneRosterSection');
    render(<OneRosterSection {...baseProps} />);
    expect(screen.getByPlaceholderText(/yoursis\.example\.com/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/OAuth 2\.0 Client ID/i)).toBeTruthy();
    expect(screen.getByText(/Save Config/i)).toBeTruthy();
    expect(screen.getByText(/Test Connection/i)).toBeTruthy();
    expect(screen.getByText(/Sync Roster/i)).toBeTruthy();
  });

  it('renders the district simplified view when districtSisProvider is oneroster', async () => {
    const { default: OneRosterSection } = await import('../components/settings-classroom/OneRosterSection');
    render(<OneRosterSection {...baseProps} districtSisProvider="oneroster" />);
    expect(screen.getByText(/District configured/i)).toBeTruthy();
    expect(screen.getByText(/Roster Sync/i)).toBeTruthy();
  });

  it('returns null when activeProvider is clever', async () => {
    const { default: OneRosterSection } = await import('../components/settings-classroom/OneRosterSection');
    const { container } = render(<OneRosterSection {...baseProps} activeProvider="clever" />);
    expect(container.firstChild).toBeFalsy();
  });
});

describe('OneRosterCredentialsFields', () => {
  it('renders all six credential fields', async () => {
    const { default: OneRosterCredentialsFields } = await import('../components/settings-classroom/OneRosterCredentialsFields');
    render(
      <OneRosterCredentialsFields
        oneRosterConfig={baseConfig}
        oneRosterHasCredentials={false}
        setOneRosterConfig={vi.fn()}
        setShowOneRosterSecret={vi.fn()}
        showOneRosterSecret={false}
      />
    );
    expect(screen.getByPlaceholderText(/yoursis\.example\.com/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/OAuth 2\.0 Client ID/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/OAuth 2\.0 Client Secret/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/Defaults to base_url\/token/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/Filter roster to a specific school/i)).toBeTruthy();
    expect(screen.getByPlaceholderText(/Your OneRoster teacher sourcedId/i)).toBeTruthy();
  });

  it('shows "Credentials saved" badge when oneRosterHasCredentials is true and secret is empty', async () => {
    const { default: OneRosterCredentialsFields } = await import('../components/settings-classroom/OneRosterCredentialsFields');
    render(
      <OneRosterCredentialsFields
        oneRosterConfig={{ ...baseConfig, client_secret: '' }}
        oneRosterHasCredentials={true}
        setOneRosterConfig={vi.fn()}
        setShowOneRosterSecret={vi.fn()}
        showOneRosterSecret={false}
      />
    );
    expect(screen.getByText(/Credentials saved/i)).toBeTruthy();
  });
});

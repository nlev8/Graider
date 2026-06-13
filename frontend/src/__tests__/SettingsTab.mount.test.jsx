import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import SettingsTab from '../tabs/SettingsTab';
import RosterMappingModal from '../tabs/settings/RosterMappingModal';
import ParentContactMappingModal from '../tabs/settings/ParentContactMappingModal';
import AddStudentModal from '../tabs/settings/AddStudentModal';
import AccommodationModal from '../tabs/settings/AccommodationModal';

// Render-time smoke test for SettingsTab. Added with the CQ wave-9 split of
// SettingsTab.jsx into tabs/settings/* (mirrors GradeTab.mount.test.jsx from
// the wave-2 grade split, added for the same reason): build + unit tests pass
// even if a split leaves an unimported component or mis-threaded prop that
// white-screens the tab at runtime. Mounts the real shell (sub-tab nav via
// SettingsSubTabNav, classroom glue via ClassroomSection, integration state
// via useIntegrationState, modal state via useSettingsModalsState) plus the
// four extracted shell-level modals directly (they're closed by default
// through the shell, so direct mounts assert their content).
vi.mock('../services/api', () => new Proxy({}, {
  get: (t, p) => (p === 'then' ? undefined : vi.fn().mockResolvedValue({})),
  has: () => true,
}));

const base = () => ({
  settingsTab: 'general',
  config: {},
  rubric: { categories: [] },
  globalAINotes: '',
  apiKeys: { openai: '', anthropic: '', gemini: '' },
  subscription: null,
  subscriptionLoading: false,
  periods: [],
  rosters: [],
  studentAccommodations: {},
  vportalEmail: '',
  vportalConfigured: false,
  supportDocs: [],
  assessmentTemplates: [],
  uploadingTemplate: false,
  showOnboardingWizard: false,
  sortedPeriods: [],
  accommodationPresets: [],
  EDTECH_TOOLS: [],
  MODEL_COST_PER_ASSIGNMENT: {},
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('SettingsTab mounts without crashing (render-time smoke)', () => {
  afterEach(() => {
    vi.clearAllMocks();
    delete window.__graiderUser;
  });

  it('renders the shell header + every sub-tab nav label; shell modals stay closed', () => {
    render(<SettingsTab {...makeProps()} />);

    expect(screen.getByText('Settings')).toBeTruthy();
    // SettingsSubTabNav — all seven labels (Billing visible for non-Clever users)
    for (const label of ['General', 'Grading', 'AI', 'Classroom', 'Privacy', 'Billing', 'Resources']) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    // The four shell-level modals are closed by default (useSettingsModalsState init)
    expect(screen.queryByText('Map Roster Columns')).toBeNull();
    expect(screen.queryByText('Map Parent Contact Columns')).toBeNull();
    expect(screen.queryByText('Add Student to Roster')).toBeNull();
    expect(screen.queryByText('Add Student Accommodations')).toBeNull();
  });

  it('nav buttons thread setSettingsTab through SettingsSubTabNav', () => {
    const setSettingsTab = vi.fn();
    render(<SettingsTab {...makeProps({ setSettingsTab })} />);
    fireEvent.click(screen.getByText('Privacy'));
    expect(setSettingsTab).toHaveBeenCalledWith('privacy');
  });

  it('hides the Billing sub-tab for Clever SSO users (useIntegrationState → nav threading)', () => {
    window.__graiderUser = { id: 'clever:abc123' };
    render(<SettingsTab {...makeProps()} />);
    expect(screen.queryByText('Billing')).toBeNull();
  });

  it('classroom tab renders SettingsClassroom content through ClassroomSection (spread threading)', () => {
    render(<SettingsTab {...makeProps({ settingsTab: 'classroom' })} />);
    // PeriodsSection header — deep inside SettingsClassroom, proving the
    // {...integration}/{...modals} + flat-prop threading mounts the real tree.
    expect(screen.getByText('Class Periods')).toBeTruthy();
  });

  it('RosterMappingModal renders its mapping form when shown', () => {
    render(
      <RosterMappingModal
        rosterMappingModal={{ show: true, roster: { filename: 'r.csv', headers: ['Name'], column_mapping: {} } }}
        setRosterMappingModal={vi.fn()}
        setRosters={vi.fn()}
        addToast={vi.fn()}
      />,
    );
    expect(screen.getByText('Map Roster Columns')).toBeTruthy();
    expect(screen.getByText('Save Mapping')).toBeTruthy();
  });

  it('ParentContactMappingModal renders its mapping form when shown', () => {
    render(
      <ParentContactMappingModal
        parentContactMapping={{
          show: true,
          preview: { sheets: [{ name: 'Period 1', row_count: 3, headers: ['Student', 'Email'] }] },
          mapping: {},
        }}
        setParentContactMapping={vi.fn()}
        uploadingParentContacts={false}
        setUploadingParentContacts={vi.fn()}
        setParentContacts={vi.fn()}
        addToast={vi.fn()}
      />,
    );
    expect(screen.getByText('Map Parent Contact Columns')).toBeTruthy();
    expect(screen.getByText('3 rows detected')).toBeTruthy();
    expect(screen.getByText('Save & Import')).toBeTruthy();
  });

  it('AddStudentModal renders extracted student fields when shown', () => {
    render(
      <AddStudentModal
        addStudentModal={{ show: true, loading: false, image: null, error: null, student: { first_name: 'Ada', period: '2' } }}
        setAddStudentModal={vi.fn()}
        addToast={vi.fn()}
      />,
    );
    expect(screen.getByText('Add Student to Roster')).toBeTruthy();
    expect(screen.getByText('Add to Period 2')).toBeTruthy();
  });

  it('AccommodationModal renders pickers + notes + actions when shown', () => {
    render(
      <AccommodationModal
        accommodationModal={{ show: true, studentId: null }}
        setAccommodationModal={vi.fn()}
        accommEllLanguage=""
        setAccommEllLanguage={vi.fn()}
        accommPeriodFilter=""
        setAccommPeriodFilter={vi.fn()}
        accommSelectedStudents={{}}
        setAccommSelectedStudents={vi.fn()}
        accommStudentsList={[]}
        setAccommStudentsList={vi.fn()}
        accommodationCustomNotes=""
        setAccommodationCustomNotes={vi.fn()}
        selectedAccommodationPresets={[]}
        setSelectedAccommodationPresets={vi.fn()}
        accommodationPresets={[{ id: 'ell_support', name: 'ELL Support', description: 'Language support', icon: 'FileText' }]}
        sortedPeriods={[]}
        setStudentAccommodations={vi.fn()}
        addToast={vi.fn()}
      />,
    );
    expect(screen.getByText('Add Student Accommodations')).toBeTruthy();
    // AccommodationStudentPicker (studentId null → picker shown)
    expect(screen.getByText('Select Students')).toBeTruthy();
    // AccommodationPresetPicker
    expect(screen.getByText('ELL Support')).toBeTruthy();
    expect(screen.getByText('Language support')).toBeTruthy();
    // FERPA note + actions stay in the modal shell
    expect(screen.getByText(/FERPA Compliant/)).toBeTruthy();
    expect(screen.getByText('Save Accommodations')).toBeTruthy();
  });
});

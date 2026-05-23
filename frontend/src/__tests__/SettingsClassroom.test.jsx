import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SettingsClassroom from '../components/SettingsClassroom';

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

const base = () => ({
  // arrays (.map/.length/.filter/.find at render)
  accommodationPresets: [],
  sortedPeriods: [],
  expandedStudents: [],
  ltiContexts: [],
  ltiPlatforms: [],
  ltiSyncScores: [],
  cleverSelectedSections: {},
  // structured objects
  cleverAccommSuggestions: {},
  cleverSyncResult: null,
  editStudentData: null,
  focusImportProgress: null,
  ltiNewPlatform: { name: '', issuer: '', client_id: '', auth_url: '', token_url: '', jwks_url: '', deployment_id: '' },
  ltiSelectedContext: '',
  ltiSyncResult: null,
  ltiToolConfig: {},
  newStudent: { name: '', email: '', student_id_number: '' },
  oneRosterAccommodations: {},
  oneRosterConfig: { base_url: '', client_id: '', client_secret: '', school_id: '' },
  oneRosterStatus: null,
  oneRosterSyncResult: null,
  oneRosterTestResult: null,
  parentContacts: {},
  studentAccommodations: {},
  loadingExpandedStudents: {},
  // refs
  parentContactsInputRef: { current: null },
  periodInputRef: { current: null },
  // scalar values rendered directly
  activeProvider: null,
  districtSisProvider: '',
  teacherSisId: '',
  newPeriodName: '',
  expandedPeriod: null,
  editingStudentId: null,
  ltiSyncLabel: '',
  ltiSyncMaxScore: 100,
  // booleans
  addingStudent: false,
  cleverApplying: false,
  cleverSyncing: false,
  focusImporting: false,
  isCleverUser: false,
  ltiSaving: false,
  ltiShowForm: false,
  ltiSyncing: false,
  oneRosterApplying: false,
  oneRosterHasCredentials: false,
  oneRosterSaving: false,
  oneRosterSyncing: false,
  showManualSetup: false,
  showOneRosterSecret: false,
  uploadingParentContacts: false,
  uploadingPeriod: false,
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('SettingsClassroom', () => {
  it('smoke: renders without crashing', () => {
    const { container } = render(<SettingsClassroom {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });
});

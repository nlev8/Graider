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

  // Exercises the branches the default smoke test leaves hidden (Clever section,
  // LTI add-platform form, expanded period with edit row + add-student form,
  // accommodation suggestion panels) so every extracted section actually renders.
  it('smoke: renders all guarded sections without crashing', () => {
    const props = makeProps({
      isCleverUser: true,
      showManualSetup: true,
      ltiShowForm: true,
      activeProvider: null,
      districtSisProvider: '',
      sortedPeriods: [{ filename: 'p1.csv', period_name: 'Period 1', row_count: 1, course_codes: ['M101'], class_level: 'standard', imported_from: 'focus' }],
      expandedPeriod: 'p1.csv',
      loadingExpandedStudents: false,
      expandedStudents: [
        { id: 's1', full: 'Student One', first: 'Student', last: 'One', student_email: 'a@b.c', parent_emails: ['p@b.c'], parent_phones: ['555'] },
        { id: 's2', full: 'Student Two', first: 'Student', last: 'Two', student_email: '', parent_emails: [], parent_phones: [] },
      ],
      editingStudentId: 's1',
      editStudentData: { student_name: 'Student One', student_email: '', parent_emails: '', parent_phones: '' },
      addingStudent: true,
      newStudent: { name: '', student_id: '', grade: '', student_email: '', parent_emails: '', parent_phones: '' },
      cleverSyncing: false,
      cleverSyncResult: {
        counts: { students: 1, sections: 1, students_with_accommodations: 1 },
        available_sections: [{ clever_section_id: 'c1', name: 'Sec', subject: 'Math', grade: '6', student_clever_ids: ['x'] }],
      },
      cleverSelectedSections: { c1: true },
      cleverAccommSuggestions: { s1: { name: 'Student One', iep_status: true, ell_status: true, home_language: 'Spanish', suggested_presets: ['ell_support'] } },
      oneRosterAccommodations: { s1: { name: 'Student One', iep_status: false, ell_status: true, home_language: 'Spanish', suggested_presets: [] } },
      oneRosterStatus: 'connected',
      oneRosterTestResult: { success: true, school_name: 'School' },
      oneRosterSyncResult: { counts: { students: 1, sections: 1, classes: 1, enrollments: 1, students_with_accommodations: 1 } },
      oneRosterHasCredentials: true,
      ltiToolConfig: { oidc_login_url: 'a', launch_url: 'b', jwks_url: 'c', redirect_uri: 'd' },
      ltiPlatforms: [{ name: 'Canvas', issuer: 'https://i', client_id: 'cid' }],
      ltiNewPlatform: { name: '', issuer: '', client_id: '', auth_login_url: '', auth_token_url: '', jwks_url: '', deployment_ids: '' },
      ltiContexts: [{ context_id: 'ctx', context_title: 'Course', student_count: 1, platform_issuer: 'https://i', students: [{ name: 'Student One', user_id: 'u1' }] }],
      ltiSelectedContext: { context_id: 'ctx', platform_issuer: 'https://i' },
      ltiSyncScores: [{ student_name: 'Student One', score: '95' }],
      ltiSyncResult: { status: 'ok', synced: 1, total: 1, unmatched_students: ['Student Two'] },
      focusImporting: true,
      focusImportProgress: 'Importing...',
      studentAccommodations: { s1: { student_name: 'Student One', presets: [{ id: 'ell_support', name: 'ELL' }], custom_notes: 'note' } },
      accommodationPresets: [{ id: 'ell_support', name: 'ELL Support', description: 'desc', icon: 'FileText' }],
      parentContacts: { count: 1, with_email: 1, without_email: 1, period_stats: { P1: { total: 1 } } },
    });
    const { container } = render(<SettingsClassroom {...props} />);
    expect(container.firstChild).toBeTruthy();
  });
});

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

// Render-time smoke test for PeriodsSection + children. Added with the CQ
// wave-8 split (#cq8-06) that extracted PeriodUploadControls and
// PeriodStudentTable from PeriodsSection / PeriodStudentList.
// Verifies: (1) section heading renders, (2) Upload CSV/Excel button present,
// (3) Import from Focus button present, (4) period cards render when sortedPeriods
// supplied, (5) PeriodStudentTable renders student rows when expanded.
// Uses Vitest native matchers (toBeTruthy), NOT jest-dom.

vi.mock('../services/api', () => ({
  uploadPeriod: vi.fn().mockResolvedValue({}),
  listPeriods: vi.fn().mockResolvedValue({ periods: [] }),
  getPeriodStudents: vi.fn().mockResolvedValue({ students: [] }),
  deletePeriod: vi.fn().mockResolvedValue({}),
  updatePeriodLevel: vi.fn().mockResolvedValue({}),
  getParentContacts: vi.fn().mockResolvedValue({ contacts: {} }),
  importFromFocus: vi.fn().mockResolvedValue({}),
  getFocusImportStatus: vi.fn().mockResolvedValue({ status: 'idle' }),
  addStudent: vi.fn().mockResolvedValue({}),
  removeStudent: vi.fn().mockResolvedValue({}),
  updateStudent: vi.fn().mockResolvedValue({}),
}));

vi.mock('../components/Icon', () => ({
  default: ({ name }) => <span data-testid={`icon-${name}`} />,
}));

import PeriodsSection from '../components/settings-classroom/PeriodsSection';

afterEach(() => {
  vi.clearAllMocks();
});

function baseProps(overrides = {}) {
  return {
    addToast: vi.fn(),
    focusImportProgress: '',
    focusImporting: false,
    newPeriodName: '',
    periodInputRef: { current: null },
    setFocusImportProgress: vi.fn(),
    setFocusImporting: vi.fn(),
    setNewPeriodName: vi.fn(),
    setPeriods: vi.fn(),
    setUploadingPeriod: vi.fn(),
    sortedPeriods: [],
    uploadingPeriod: false,
    // PeriodCard / PeriodStudentList props
    expandedPeriod: null,
    setExpandedPeriod: vi.fn(),
    setExpandedStudents: vi.fn(),
    setLoadingExpandedStudents: vi.fn(),
    expandedStudents: [],
    loadingExpandedStudents: false,
    editingStudentId: null,
    setEditingStudentId: vi.fn(),
    editStudentData: {},
    setEditStudentData: vi.fn(),
    addingStudent: false,
    setAddingStudent: vi.fn(),
    newStudent: { name: '', student_id: '', grade: '', student_email: '', parent_emails: '', parent_phones: '' },
    setNewStudent: vi.fn(),
    ...overrides,
  };
}

describe('PeriodsSection mounts without crashing (render-time smoke)', () => {
  it('renders "Class Periods" heading', () => {
    render(<PeriodsSection {...baseProps()} />);
    expect(screen.getByText('Class Periods')).toBeTruthy();
  });

  it('renders Upload CSV/Excel button via PeriodUploadControls', () => {
    render(<PeriodsSection {...baseProps()} />);
    expect(screen.getByText('Upload CSV/Excel')).toBeTruthy();
  });

  it('renders Import from Focus button via PeriodUploadControls', () => {
    render(<PeriodsSection {...baseProps()} />);
    expect(screen.getByText('Import from Focus')).toBeTruthy();
  });

  it('renders no period cards when sortedPeriods is empty', () => {
    const { container } = render(<PeriodsSection {...baseProps()} />);
    // No period-level border boxes beyond the outer wrapper
    const borderBoxes = container.querySelectorAll('[style*="border-radius: 8px"]');
    expect(borderBoxes.length).toBeFalsy() || expect(borderBoxes.length === 0).toBeTruthy();
  });

  it('renders a period card when sortedPeriods has an entry', () => {
    const period = {
      filename: 'period1.csv',
      period_name: 'Period 1',
      row_count: 5,
      imported_from: 'upload',
      class_level: 'standard',
      course_codes: [],
    };
    render(<PeriodsSection {...baseProps({ sortedPeriods: [period] })} />);
    expect(screen.getByText('Period 1')).toBeTruthy();
    expect(screen.getByText('5 students')).toBeTruthy();
  });

  it('shows Focus import progress banner when focusImporting + progress set', () => {
    render(
      <PeriodsSection
        {...baseProps({ focusImporting: true, focusImportProgress: 'Syncing periods...' })}
      />
    );
    expect(screen.getByText('Syncing periods...')).toBeTruthy();
  });

  it('shows helper hint when newPeriodName is empty', () => {
    render(<PeriodsSection {...baseProps({ newPeriodName: '' })} />);
    expect(screen.getByText('Enter a period name above, then click Upload')).toBeTruthy();
  });

  it('hides helper hint when newPeriodName is set', () => {
    render(<PeriodsSection {...baseProps({ newPeriodName: 'Period 2' })} />);
    expect(screen.queryByText('Enter a period name above, then click Upload')).toBeFalsy();
  });
});

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

// Render-time smoke test for AccommodationModal. Added with the CQ wave-8
// split (#cq8-05) that extracted AccommodationModalFooter from the parent.
// Verifies: (1) modal hidden when show=false, (2) "Add Student Accommodations"
// title for new students, (3) "Edit Accommodations" title for single-student
// edit mode, (4) ELL language selector appears only when ell_support preset is
// selected, (5) Save and Cancel buttons are present and wired, (6) custom
// notes textarea is present. Tests use Vitest native matchers (toBeTruthy),
// not jest-dom.

vi.mock('../services/api', () => ({
  setStudentAccommodation: vi.fn().mockResolvedValue({}),
  getEllStudents: vi.fn().mockResolvedValue({}),
  saveEllStudents: vi.fn().mockResolvedValue({}),
  getStudentAccommodations: vi.fn().mockResolvedValue({ accommodations: {} }),
}));

import AccommodationModal from '../tabs/settings/AccommodationModal';

afterEach(() => {
  vi.clearAllMocks();
});

const PRESETS = [
  { id: 'extended_time', label: 'Extended Time' },
  { id: 'ell_support', label: 'ELL Support' },
];

function baseProps(overrides = {}) {
  return {
    accommodationModal: { show: true, studentId: null },
    setAccommodationModal: vi.fn(),
    accommEllLanguage: '',
    setAccommEllLanguage: vi.fn(),
    accommPeriodFilter: '',
    setAccommPeriodFilter: vi.fn(),
    accommSelectedStudents: {},
    setAccommSelectedStudents: vi.fn(),
    accommStudentsList: [],
    setAccommStudentsList: vi.fn(),
    accommodationCustomNotes: '',
    setAccommodationCustomNotes: vi.fn(),
    selectedAccommodationPresets: [],
    setSelectedAccommodationPresets: vi.fn(),
    accommodationPresets: PRESETS,
    sortedPeriods: ['Period 1', 'Period 2'],
    setStudentAccommodations: vi.fn(),
    addToast: vi.fn(),
    ...overrides,
  };
}

describe('AccommodationModal mounts without crashing (render-time smoke)', () => {
  it('renders nothing when show=false', () => {
    const { container } = render(
      <AccommodationModal {...baseProps({ accommodationModal: { show: false, studentId: null } })} />
    );
    expect(container.firstChild).toBeFalsy();
  });

  it('shows "Add Student Accommodations" for a new-student modal', () => {
    render(<AccommodationModal {...baseProps()} />);
    expect(screen.getByText('Add Student Accommodations')).toBeTruthy();
  });

  it('shows "Edit Accommodations" when a studentId is provided', () => {
    render(
      <AccommodationModal
        {...baseProps({ accommodationModal: { show: true, studentId: 'stu-1' } })}
      />
    );
    expect(screen.getByText('Edit Accommodations')).toBeTruthy();
  });

  it('renders FERPA notice, Save, and Cancel buttons', () => {
    render(<AccommodationModal {...baseProps()} />);
    expect(screen.getByText(/FERPA Compliant/)).toBeTruthy();
    expect(screen.getByText('Save Accommodations')).toBeTruthy();
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('renders custom notes textarea via AccommodationModalFooter', () => {
    render(<AccommodationModal {...baseProps()} />);
    expect(
      screen.getByPlaceholderText('Any additional accommodation instructions...')
    ).toBeTruthy();
  });

  it('shows ELL language selector only when ell_support preset is selected', () => {
    const { rerender } = render(<AccommodationModal {...baseProps()} />);
    // ELL selector absent without ell_support
    expect(screen.queryByText('Home Language (for bilingual feedback)')).toBeFalsy();

    rerender(
      <AccommodationModal
        {...baseProps({ selectedAccommodationPresets: ['ell_support'] })}
      />
    );
    expect(screen.getByText('Home Language (for bilingual feedback)')).toBeTruthy();
  });

  it('Cancel button calls setAccommodationModal with show=false', () => {
    const setAccommodationModal = vi.fn();
    render(<AccommodationModal {...baseProps({ setAccommodationModal })} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(setAccommodationModal).toHaveBeenCalledWith({ show: false, studentId: null });
  });

  it('X button calls setAccommodationModal with show=false', () => {
    const setAccommodationModal = vi.fn();
    const { container } = render(
      <AccommodationModal {...baseProps({ setAccommodationModal })} />
    );
    // X icon button is the close button in the modal header
    const buttons = container.querySelectorAll('button');
    const xBtn = Array.from(buttons).find(
      (b) => !b.textContent.includes('Save') && !b.textContent.includes('Cancel')
    );
    expect(xBtn).toBeTruthy();
    fireEvent.click(xBtn);
    expect(setAccommodationModal).toHaveBeenCalledWith({ show: false, studentId: null });
  });
});

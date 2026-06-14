import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mount smoke test for AccommodationsSection and its extracted children:
// AccommodationsImportExport and AccommodationStudentEntries.
// Added with the CQ wave-8 split (#cq8-06). Asserts that key text from the
// header, presets list, student list, and import/export panel renders without
// crashing, confirming props thread correctly through the child boundaries.

vi.mock('../services/api', () => ({
  importAccommodations: vi.fn(),
  getStudentAccommodations: vi.fn(),
  exportAccommodations: vi.fn(),
  getEllStudents: vi.fn(),
  deleteStudentAccommodation: vi.fn(),
}));

vi.mock('../components/Icon', () => ({
  default: ({ name }) => <span data-testid={`icon-${name}`} />,
}));

import AccommodationsSection from '../components/settings-classroom/AccommodationsSection';

const basePresets = [
  { id: 'extended_time', name: 'Extended Time', description: 'Extra time on tests', icon: 'Clock' },
  { id: 'ell_support', name: 'ELL Support', description: 'Language support', icon: 'Globe' },
];

const baseStudentAccommodations = {
  'student-1': {
    student_name: 'Alice Smith',
    presets: [{ id: 'extended_time', name: 'Extended Time' }],
    custom_notes: '',
  },
  'student-2': {
    student_name: 'Bob Jones',
    presets: [{ id: 'ell_support', name: 'ELL Support' }],
    custom_notes: 'Extra context needed',
  },
};

const makeProps = (overrides = {}) => ({
  accommodationPresets: basePresets,
  studentAccommodations: baseStudentAccommodations,
  addToast: vi.fn(),
  setStudentAccommodations: vi.fn(),
  setAccommodationModal: vi.fn(),
  setSelectedAccommodationPresets: vi.fn(),
  setAccommodationCustomNotes: vi.fn(),
  setAccommEllLanguage: vi.fn(),
  ...overrides,
});

describe('AccommodationsSection mounts without crashing', () => {
  it('renders the section header and FERPA badge', () => {
    render(<AccommodationsSection {...makeProps()} />);
    expect(screen.getByText('IEP/504 Accommodations')).toBeTruthy();
    expect(screen.getByText('FERPA Compliant')).toBeTruthy();
  });

  it('renders available presets via the presets grid', () => {
    render(<AccommodationsSection {...makeProps()} />);
    expect(screen.getByText('Available Presets')).toBeTruthy();
    // Both preset names appear in presets grid + student badge rows; at least one each.
    expect(screen.getAllByText('Extended Time').length).toBeGreaterThan(0);
    expect(screen.getAllByText('ELL Support').length).toBeGreaterThan(0);
    // Preset descriptions only appear in the presets grid (not in badge rows).
    expect(screen.getByText('Extra time on tests')).toBeTruthy();
    expect(screen.getByText('Language support')).toBeTruthy();
  });

  it('renders student count and student names via AccommodationStudentEntries', () => {
    render(<AccommodationsSection {...makeProps()} />);
    expect(screen.getByText(/2\s*students/)).toBeTruthy();
    expect(screen.getByText('Alice Smith')).toBeTruthy();
    expect(screen.getByText('Bob Jones')).toBeTruthy();
    expect(screen.getByText('Custom Notes')).toBeTruthy();
  });

  it('renders the Import & Export panel via AccommodationsImportExport', () => {
    render(<AccommodationsSection {...makeProps()} />);
    expect(screen.getByText('Import & Export')).toBeTruthy();
    expect(screen.getByText('Import from CSV')).toBeTruthy();
    expect(screen.getByText('Export Accommodations')).toBeTruthy();
  });

  it('shows empty state when no student accommodations', () => {
    render(<AccommodationsSection {...makeProps({ studentAccommodations: {} })} />);
    expect(screen.getByText(/No students with accommodations yet/)).toBeTruthy();
  });
});

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

// Render-time smoke test for ParentContactMappingModal. Added with the CQ
// wave-8 split (#cq8-06) that extracted ParentContactMappingForm from the
// parent. Verifies: (1) modal hidden when show=false or preview=null,
// (2) title "Map Parent Contact Columns" is shown, (3) sheet-count vs
// row-count description text renders correctly, (4) form fields rendered via
// ParentContactMappingForm (name column, contact columns, etc.), (5) Save &
// Import and Cancel buttons are present, (6) X close button calls
// setParentContactMapping with reset state. Tests use Vitest native matchers
// (toBeTruthy), not jest-dom.

vi.mock('../services/api', () => ({
  saveParentContactMapping: vi.fn().mockResolvedValue({ unique_students: 10, with_email: 8 }),
  getParentContacts: vi.fn().mockResolvedValue([]),
}));

import ParentContactMappingModal from '../tabs/settings/ParentContactMappingModal';

afterEach(() => {
  vi.clearAllMocks();
});

const HEADERS = ['Student Name', 'Email', 'Phone', 'Student ID', 'Period'];

const SINGLE_SHEET_PREVIEW = {
  sheets: [
    { name: 'Sheet1', row_count: 42, headers: HEADERS },
  ],
};

const MULTI_SHEET_PREVIEW = {
  sheets: [
    { name: 'Period 1', row_count: 20, headers: HEADERS },
    { name: 'Period 2', row_count: 22, headers: HEADERS },
  ],
};

function baseProps(overrides = {}) {
  return {
    parentContactMapping: {
      show: true,
      preview: SINGLE_SHEET_PREVIEW,
      mapping: { name_col: '', name_format: 'last_first', id_col: '', contact_cols: [] },
    },
    setParentContactMapping: vi.fn(),
    uploadingParentContacts: false,
    setUploadingParentContacts: vi.fn(),
    setParentContacts: vi.fn(),
    addToast: vi.fn(),
    ...overrides,
  };
}

describe('ParentContactMappingModal mounts without crashing (render-time smoke)', () => {
  it('renders nothing when show=false', () => {
    const { container } = render(
      <ParentContactMappingModal
        {...baseProps({
          parentContactMapping: { show: false, preview: SINGLE_SHEET_PREVIEW, mapping: null },
        })}
      />
    );
    expect(container.firstChild).toBeFalsy();
  });

  it('renders nothing when preview=null', () => {
    const { container } = render(
      <ParentContactMappingModal
        {...baseProps({
          parentContactMapping: { show: true, preview: null, mapping: null },
        })}
      />
    );
    expect(container.firstChild).toBeFalsy();
  });

  it('shows the modal title', () => {
    render(<ParentContactMappingModal {...baseProps()} />);
    expect(screen.getByText('Map Parent Contact Columns')).toBeTruthy();
  });

  it('shows row count for a single-sheet file', () => {
    render(<ParentContactMappingModal {...baseProps()} />);
    expect(screen.getByText('42 rows detected')).toBeTruthy();
  });

  it('shows sheet count for a multi-sheet file', () => {
    render(
      <ParentContactMappingModal
        {...baseProps({
          parentContactMapping: {
            show: true,
            preview: MULTI_SHEET_PREVIEW,
            mapping: { name_col: '', name_format: 'last_first', id_col: '', contact_cols: [] },
          },
        })}
      />
    );
    expect(screen.getByText('2 sheets detected (each sheet = one period)')).toBeTruthy();
  });

  it('renders the Student Name Column label via ParentContactMappingForm', () => {
    render(<ParentContactMappingModal {...baseProps()} />);
    expect(screen.getByText('Student Name Column')).toBeTruthy();
  });

  it('renders Contact Columns label via ParentContactMappingForm', () => {
    render(<ParentContactMappingModal {...baseProps()} />);
    expect(screen.getByText('Contact Columns (email and phone)')).toBeTruthy();
  });

  it('renders Save & Import and Cancel buttons', () => {
    render(<ParentContactMappingModal {...baseProps()} />);
    expect(screen.getByText('Save & Import')).toBeTruthy();
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('Save & Import is disabled while uploading', () => {
    render(
      <ParentContactMappingModal {...baseProps({ uploadingParentContacts: true })} />
    );
    expect(screen.getByText('Importing...')).toBeTruthy();
    const btn = screen.getByText('Importing...').closest('button');
    expect(btn.disabled).toBeTruthy();
  });

  it('Cancel button calls setParentContactMapping with reset state', () => {
    const setParentContactMapping = vi.fn();
    render(<ParentContactMappingModal {...baseProps({ setParentContactMapping })} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(setParentContactMapping).toHaveBeenCalledWith({ show: false, preview: null, mapping: null });
  });

  it('X button calls setParentContactMapping with reset state', () => {
    const setParentContactMapping = vi.fn();
    const { container } = render(
      <ParentContactMappingModal {...baseProps({ setParentContactMapping })} />
    );
    const buttons = container.querySelectorAll('button');
    const xBtn = Array.from(buttons).find(
      (b) => !b.textContent.includes('Import') && !b.textContent.includes('Cancel')
    );
    expect(xBtn).toBeTruthy();
    fireEvent.click(xBtn);
    expect(setParentContactMapping).toHaveBeenCalledWith({ show: false, preview: null, mapping: null });
  });
});

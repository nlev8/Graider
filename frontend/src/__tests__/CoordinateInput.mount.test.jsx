import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CoordinateInput from '../components/CoordinateInput.jsx';

// Render-equivalence net for CoordinateInput + CoordinateDmsInput child.
// Added with the CQ wave-2 split of CoordinateInput.jsx (233→169 LOC) —
// the DMS input panel was extracted to coordinate-input/CoordinateDmsInput.jsx.
// This test mounts the full tree and asserts key landmarks are present in each
// format mode, ensuring the prop-threading to the child is wired correctly.

describe('CoordinateInput', () => {
  it('renders the format selector', () => {
    render(<CoordinateInput onChange={vi.fn()} />);
    expect(screen.getByText('Format:')).toBeTruthy();
  });

  it('renders decimal degree inputs by default', () => {
    render(<CoordinateInput onChange={vi.fn()} />);
    expect(screen.getByText('Latitude:')).toBeTruthy();
    expect(screen.getByText('Longitude:')).toBeTruthy();
  });

  it('renders optional label when provided', () => {
    render(<CoordinateInput onChange={vi.fn()} label="Enter location" />);
    expect(screen.getByText('Enter location')).toBeTruthy();
  });

  it('renders DMS child panel (Convert to Decimal button) when format is dms', () => {
    render(<CoordinateInput onChange={vi.fn()} />);
    const select = screen.getAllByRole('combobox')[0];
    fireEvent.change(select, { target: { value: 'dms' } });
    // Convert to Decimal button lives in CoordinateDmsInput — confirms child renders
    expect(screen.getByText('Convert to Decimal')).toBeTruthy();
  });
});

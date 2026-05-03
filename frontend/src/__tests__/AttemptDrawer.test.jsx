/**
 * AttemptDrawer component tests.
 *
 * Proof-of-concept for component-level test coverage of the App.jsx
 * extractions (#157-168). AttemptDrawer was the cleanest extraction
 * target: pure presentational, 2-prop surface (student, onClose), no
 * async/closures.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import AttemptDrawer from '../components/AttemptDrawer';

const sampleStudent = {
  student_name: 'Jane Doe',
  attempts: [
    {
      submission_id: 's1',
      attempt_number: 1,
      percentage: 87.5,
      score: 35,
      total_points: 40,
      submitted_at: '2026-05-01T15:30:00Z',
      time_taken_seconds: 125, // 2m 5s
    },
    {
      submission_id: 's2',
      attempt_number: 2,
      percentage: null,
      score: null,
      total_points: null,
      submitted_at: null,
      time_taken_seconds: null,
    },
  ],
};

describe('AttemptDrawer', () => {
  it('renders nothing when student is null', () => {
    const { container } = render(<AttemptDrawer student={null} onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders the student name and attempt count', () => {
    render(<AttemptDrawer student={sampleStudent} onClose={() => {}} />);
    expect(screen.getByText('Jane Doe')).toBeDefined();
    expect(screen.getByText('2 attempts')).toBeDefined();
  });

  it('renders each attempt with formatted percentage and score', () => {
    render(<AttemptDrawer student={sampleStudent} onClose={() => {}} />);

    // First attempt — 87.5% rounds to 88%
    expect(screen.getByText('Attempt 1')).toBeDefined();
    expect(screen.getByText('88%')).toBeDefined();
    expect(screen.getByText('Score: 35 / 40')).toBeDefined();

    // Second attempt — nulls render as em-dash, no Score row
    expect(screen.getByText('Attempt 2')).toBeDefined();
    const emDashes = screen.getAllByText((_, node) =>
      Boolean(node && node.textContent && node.textContent.includes(String.fromCharCode(8212)))
    );
    expect(emDashes.length).toBeGreaterThan(0);
  });

  it('calls onClose when the backdrop is clicked', () => {
    const onClose = vi.fn();
    const { container } = render(<AttemptDrawer student={sampleStudent} onClose={onClose} />);
    const backdrop = container.firstChild;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does NOT call onClose when the inner card is clicked', () => {
    const onClose = vi.fn();
    render(<AttemptDrawer student={sampleStudent} onClose={onClose} />);
    fireEvent.click(screen.getByText('Jane Doe'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('calls onClose when the X button is clicked', () => {
    const onClose = vi.fn();
    render(<AttemptDrawer student={sampleStudent} onClose={onClose} />);
    // The X glyph is U+2715 (10005)
    const xButton = screen.getByText(String.fromCharCode(10005));
    fireEvent.click(xButton);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('formats the time-taken as Xm Ys', () => {
    render(<AttemptDrawer student={sampleStudent} onClose={() => {}} />);
    // 125 seconds → "2m 5s"
    const matches = screen.getAllByText((_, node) =>
      Boolean(node && node.textContent && node.textContent.includes('2m 5s'))
    );
    expect(matches.length).toBeGreaterThan(0);
  });
});

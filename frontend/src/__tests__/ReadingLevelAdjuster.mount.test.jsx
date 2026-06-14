import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

// Render-time smoke test for ReadingLevelAdjuster. Added with the CQ wave-8
// split (#cq8-07) that extracted ReadingLevelUploadPanel and
// ReadingLevelResultPanel from the parent. Verifies: (1) heading present,
// (2) description text present, (3) drop-zone upload prompt present,
// (4) textarea present, (5) Adjust button present and initially disabled,
// (6) Target Level select present. Tests use Vitest native matchers
// (toBeTruthy / toBeFalsy), not jest-dom.

vi.mock('../services/api', () => ({
  extractTextFromFile: vi.fn().mockResolvedValue({ text: 'extracted' }),
  adjustReadingLevel: vi.fn().mockResolvedValue({ adjusted_text: 'adjusted', reading_level_estimate: 'Grade 6' }),
}));

import ReadingLevelAdjuster from '../components/planner-tools/ReadingLevelAdjuster';

afterEach(() => {
  vi.clearAllMocks();
});

function baseProps(overrides = {}) {
  return {
    config: { subject: 'English' },
    addToast: vi.fn(),
    ...overrides,
  };
}

describe('ReadingLevelAdjuster mounts without crashing (render-time smoke)', () => {
  it('renders the heading', () => {
    render(<ReadingLevelAdjuster {...baseProps()} />);
    expect(screen.getByText('Reading Level Adjuster')).toBeTruthy();
  });

  it('renders the description text', () => {
    render(<ReadingLevelAdjuster {...baseProps()} />);
    expect(screen.getByText(/Upload documents or screenshots/)).toBeTruthy();
  });

  it('renders the drop-zone upload prompt via ReadingLevelUploadPanel', () => {
    render(<ReadingLevelAdjuster {...baseProps()} />);
    expect(screen.getByText('Drop files here or click to upload')).toBeTruthy();
  });

  it('renders the text input textarea', () => {
    render(<ReadingLevelAdjuster {...baseProps()} />);
    expect(screen.getByPlaceholderText(/Paste text here/)).toBeTruthy();
  });

  it('renders the Adjust button (disabled when input is empty)', () => {
    render(<ReadingLevelAdjuster {...baseProps()} />);
    const btn = screen.getByRole('button', { name: /Adjust/ });
    expect(btn).toBeTruthy();
    expect(btn.disabled).toBeTruthy();
  });

  it('renders the Target Level select', () => {
    render(<ReadingLevelAdjuster {...baseProps()} />);
    expect(screen.getByText('Target Level')).toBeTruthy();
    expect(screen.getByRole('combobox')).toBeTruthy();
  });

  it('renders the Key Terms to Preserve input', () => {
    render(<ReadingLevelAdjuster {...baseProps()} />);
    expect(screen.getByPlaceholderText('Type term and press Enter')).toBeTruthy();
  });
});

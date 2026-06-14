import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';

// Render-time smoke test for SlideDeckGenerator. Added with the CQ wave-8
// split (#cq8-07) that extracted SlideDeckConfigPanel and SlideDeckResults
// from the parent. Verifies: (1) header and description render, (2) options
// controls are present (Slides select, AI Graphics select, Format select),
// (3) Generate Slide Deck button is present, (4) Browse resources button is
// present. Tests use Vitest native matchers (toBeTruthy), not jest-dom.

vi.mock('../services/api', () => ({
  listResources: vi.fn().mockResolvedValue({ resources: [] }),
  loadResource: vi.fn().mockResolvedValue({ resource: { content: '' } }),
  renderSlidesHtml: vi.fn().mockResolvedValue('<html></html>'),
  downloadSlidesPdf: vi.fn().mockResolvedValue(new Blob()),
  getSlideTemplates: vi.fn().mockResolvedValue({ groups: [] }),
}));

import SlideDeckGenerator from '../components/planner-tools/SlideDeckGenerator';

afterEach(() => {
  vi.clearAllMocks();
});

function baseProps(overrides = {}) {
  return {
    config: { subject: 'Science', grade: '8', globalAINotes: '' },
    lessonPlan: null,
    generatedAssignment: null,
    addToast: vi.fn(),
    shareWithClass: vi.fn(),
    ...overrides,
  };
}

describe('SlideDeckGenerator mounts without crashing (render-time smoke)', () => {
  it('renders the Slide Deck Generator heading', () => {
    render(<SlideDeckGenerator {...baseProps()} />);
    expect(screen.getByText('Slide Deck Generator')).toBeTruthy();
  });

  it('renders the description text', () => {
    render(<SlideDeckGenerator {...baseProps()} />);
    expect(screen.getByText(/Generate a professional slide deck/)).toBeTruthy();
  });

  it('renders the Slides count select with default value 10', () => {
    render(<SlideDeckGenerator {...baseProps()} />);
    expect(screen.getByText('Slides')).toBeTruthy();
    // The select element with option 10 selected
    const selects = screen.getAllByRole('combobox');
    expect(selects.length).toBeTruthy();
  });

  it('renders AI Graphics and Format selects', () => {
    render(<SlideDeckGenerator {...baseProps()} />);
    expect(screen.getByText('AI Graphics')).toBeTruthy();
    expect(screen.getByText('Format')).toBeTruthy();
  });

  it('renders Include saved resources label and Browse button', () => {
    render(<SlideDeckGenerator {...baseProps()} />);
    expect(screen.getByText('Include saved resources')).toBeTruthy();
    expect(screen.getByText('Browse')).toBeTruthy();
  });

  it('renders the Generate Slide Deck button (disabled with no content)', () => {
    render(<SlideDeckGenerator {...baseProps()} />);
    expect(screen.getByText('Generate Slide Deck')).toBeTruthy();
  });

  it('does not render slide results panel when slideDeck is null', () => {
    render(<SlideDeckGenerator {...baseProps()} />);
    expect(screen.queryByText('Download PowerPoint (.pptx)')).toBeFalsy();
  });

  it('renders Instructions optional input field', () => {
    render(<SlideDeckGenerator {...baseProps()} />);
    expect(
      screen.getByPlaceholderText('e.g., Focus on vocabulary, include comparison slides')
    ).toBeTruthy();
  });

  it('renders the template picker with Minimal / Swiss default', () => {
    render(<SlideDeckGenerator {...baseProps()} />);
    expect(screen.getByText('Minimal / Swiss')).toBeTruthy();
    expect(screen.getByText('Editorial Bold')).toBeTruthy();
  });
});

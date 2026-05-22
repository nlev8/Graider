import React from 'react';
import { render, fireEvent, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PlannerTools from '../components/PlannerTools';

// PlannerTools calls api.* for reading-level/resources and raw fetch for the
// study-guide/flashcards/slides generate+export endpoints. Mock both so the
// component renders in isolation.
vi.mock('../services/api', () => ({
  adjustReadingLevel: vi.fn().mockResolvedValue({ adjusted_text: 'x', reading_level_estimate: '6' }),
  extractTextFromFile: vi.fn().mockResolvedValue({ text: '' }),
  listResources: vi.fn().mockResolvedValue({ resources: [] }),
  loadResource: vi.fn().mockResolvedValue({ resource: {} }),
  saveResource: vi.fn().mockResolvedValue({ status: 'saved' }),
}));

const makeProps = (overrides = {}) => ({
  config: { subject: 'Math', grade: '8', globalAINotes: '' },
  lessonPlan: null,
  generatedAssignment: null,
  globalAINotes: '',
  uploadedDocs: [],
  addToast: vi.fn(),
  shareWithClass: vi.fn(),
  ...overrides,
});

describe('PlannerTools', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  });

  it('smoke: renders without crashing', () => {
    render(<PlannerTools {...makeProps()} />);
  });

  it('renders an input control (the reading-level tool surface)', () => {
    const { container } = render(<PlannerTools {...makeProps()} />);
    expect(container.querySelector('textarea, input')).toBeTruthy();
  });

  it('forwards shareWithClass: generate a study guide, then "Share with Class" calls the prop', async () => {
    // Regression guard for the review-caught bug: shareWithClass is a PlannerTab
    // closure forwarded as a prop; if it is not wired, the share onClick throws
    // ReferenceError at runtime (build + smoke render do not catch it).
    const shareWithClass = vi.fn();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ study_guide: { title: 'My Guide', sections: [] }, title: 'My Guide' }),
    });
    render(<PlannerTools {...makeProps({
      shareWithClass,
      lessonPlan: { title: 'My Lesson', overview: 'Intro', days: [] },
    })} />);

    fireEvent.click(screen.getByText(/Generate Study Guide/).closest('button'));
    const shareBtn = await screen.findByText('Share with Class');
    fireEvent.click(shareBtn.closest('button'));

    expect(shareWithClass).toHaveBeenCalledWith(
      { title: 'My Guide', sections: [] }, 'study_guide', 'My Guide',
    );
  });
});

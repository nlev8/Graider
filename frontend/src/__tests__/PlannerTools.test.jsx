import React from 'react';
import { render } from '@testing-library/react';
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
});

import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PlannerCalendar from '../components/PlannerCalendar';

// PlannerCalendar calls api.* for the import flow and raw fetch for calendar
// load/CRUD. Mock both so the component renders and the fetch contract is
// observable in isolation.
vi.mock('../services/api', () => ({
  listSupportDocuments: vi.fn().mockResolvedValue({ documents: [] }),
  parseDocumentForCalendar: vi.fn().mockResolvedValue({ events: [] }),
  importCalendarEvents: vi.fn().mockResolvedValue({ status: 'imported' }),
}));

const makeProps = (overrides = {}) => ({
  active: false,
  addToast: vi.fn(),
  savedLessons: [],
  supportDocs: [],
  setSupportDocs: vi.fn(),
  ...overrides,
});

describe('PlannerCalendar', () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      json: async () => ({ scheduled_lessons: [], holidays: [], school_days: {} }),
    });
  });

  it('smoke: renders without crashing when inactive', () => {
    render(<PlannerCalendar {...makeProps({ active: false })} />);
  });

  it('active=true → fetches /api/calendar on mount', async () => {
    render(<PlannerCalendar {...makeProps({ active: true })} />);
    await Promise.resolve();
    expect(global.fetch).toHaveBeenCalledWith('/api/calendar');
  });

  it('active=false → does not fetch /api/calendar on mount', async () => {
    render(<PlannerCalendar {...makeProps({ active: false })} />);
    await Promise.resolve();
    expect(global.fetch).not.toHaveBeenCalledWith('/api/calendar');
  });
});

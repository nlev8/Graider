import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
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

// Added alongside the CQ wave-5 split of PlannerCalendar.jsx into
// components/planner-calendar/* (CalendarHeader, MonthView, WeekView,
// AddEventModal, EditEventModal). The build only proves imports resolve, not
// that every relocated identifier is still in scope at render time. These
// tests mount every branch of the composed tree with real calendar data so a
// missed prop surfaces as a ReferenceError/TypeError here, not in production.
describe('PlannerCalendar branch mounts (planner-calendar/* split)', () => {
  const pad = n => String(n).padStart(2, '0');
  const fmt = d => d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());

  // nth weekday (Mon–Fri) of the current month — the component always opens on
  // the current month, and weekdays are school days when school_days is unset.
  const nthWeekdayOfCurrentMonth = (n) => {
    const now = new Date();
    let count = 0;
    for (let day = 1; day <= 28; day++) {
      const d = new Date(now.getFullYear(), now.getMonth(), day);
      if (d.getDay() >= 1 && d.getDay() <= 5) {
        count++;
        if (count === n) return d;
      }
    }
    throw new Error('unreachable');
  };

  // Wednesday of the current week — always inside the week view's visible range.
  const wednesdayThisWeek = () => {
    const d = new Date();
    d.setDate(d.getDate() - d.getDay() + 3);
    return d;
  };

  const monthLesson = () => ({
    id: 'l1', date: fmt(nthWeekdayOfCurrentMonth(1)), lesson_title: 'Algebra Review',
    unit: 'Unit 1', color: '#6366f1', day_number: 2,
  });
  const weekLesson = () => ({
    id: 'l2', date: fmt(wednesdayThisWeek()), lesson_title: 'Geometry Quiz',
    unit: 'Unit 2', color: '#22c55e',
  });
  const holiday = () => ({ date: fmt(nthWeekdayOfCurrentMonth(2)), name: 'Spring Break' });

  beforeEach(() => {
    // No school_days key → component falls back to Mon–Fri school days.
    global.fetch = vi.fn().mockResolvedValue({
      json: async () => ({
        scheduled_lessons: [monthLesson(), weekLesson()],
        holidays: [holiday()],
      }),
    });
  });

  it('mounts header with month label, view toggle, holiday + import actions', async () => {
    render(<PlannerCalendar {...makeProps({ active: true })} />);
    const monthLabel = new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    expect(await screen.findByText(monthLabel)).toBeTruthy();
    expect(screen.getByText('Today')).toBeTruthy();
    expect(screen.getByText('Month')).toBeTruthy();
    expect(screen.getByText('Week')).toBeTruthy();
    expect(screen.getByText(/Add Holiday/)).toBeTruthy();
    expect(screen.getByText('Import')).toBeTruthy();
  });

  it('mounts month view with day headers, scheduled lesson, and holiday', async () => {
    render(<PlannerCalendar {...makeProps({ active: true })} />);
    expect(await screen.findByText(/Algebra Review/)).toBeTruthy();
    expect(screen.getByText('Spring Break')).toBeTruthy();
    ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].forEach(d => {
      expect(screen.getByText(d)).toBeTruthy();
    });
  });

  it('mounts week view with lesson card, unit, and Edit/Remove actions', async () => {
    render(<PlannerCalendar {...makeProps({ active: true })} />);
    await screen.findByText(/Algebra Review/);
    fireEvent.click(screen.getByText('Week'));
    expect(await screen.findByText(/Geometry Quiz/)).toBeTruthy();
    expect(screen.getByText('Unit 2')).toBeTruthy();
    // getAllBy*: the month lesson can also land in the current week early in
    // a month, rendering a second card with its own Edit/Remove buttons.
    expect(screen.getAllByText('Edit').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Remove').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Click to add event').length).toBeGreaterThan(0);
  });

  it('opens the Add Event modal when a school-day cell is clicked', async () => {
    render(<PlannerCalendar {...makeProps({ active: true, savedLessons: { units: { 'Unit 1': [{ title: 'Saved Lesson A', filename: 'lesson-a' }] } } })} />);
    await screen.findByText(/Algebra Review/);
    // Click an empty weekday cell (no lesson on it, not the holiday).
    fireEvent.click(screen.getByText(String(nthWeekdayOfCurrentMonth(3).getDate())));
    // 'Add Event' appears twice in the modal (heading + submit button).
    expect((await screen.findAllByText('Add Event')).length).toBe(2);
    expect(screen.getByText('Custom Event')).toBeTruthy();
    expect(screen.getByPlaceholderText(/Event title/)).toBeTruthy();
    expect(screen.getByText(/Or pick from saved lessons/)).toBeTruthy();
    expect(screen.getByText('Saved Lesson A')).toBeTruthy();
  });

  it('opens the Edit Event modal when a scheduled lesson is clicked', async () => {
    render(<PlannerCalendar {...makeProps({ active: true })} />);
    fireEvent.click(await screen.findByText(/Algebra Review/));
    expect(await screen.findByText('Edit Event')).toBeTruthy();
    expect(screen.getByText('Save Changes')).toBeTruthy();
    expect(screen.getByText('Delete')).toBeTruthy();
    expect(screen.getByDisplayValue('Algebra Review')).toBeTruthy();
  });
});

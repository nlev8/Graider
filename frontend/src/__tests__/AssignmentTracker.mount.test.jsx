import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Render-equivalence net for the CQ wave cq8-04 split of AssignmentTracker.jsx:
// - AssignmentTrackerCard (291→≤200 LOC) — filter row extracted to TrackerFilters
// - PeriodMissingReport (289→≤200 LOC) — breakdown grid extracted to PeriodBreakdownGrid
//
// Mounts AssignmentTrackerCard with representative props and asserts that the
// key text / roles that were present before the split remain present after.
// Uses Vitest native matchers (no jest-dom) per project convention.

vi.mock('../components/Icon', () => ({
  default: ({ name }) => <span data-testid={`icon-${name}`} />,
}));

const BASE_PROPS = {
  periodStudentMap: {},
  sortedPeriods: [],
  savedAssignments: [],
  savedAssignmentData: {},
  addToast: vi.fn(),
  periods: [],
};

describe('AssignmentTrackerCard mount (render-equivalence net)', () => {
  it('renders the card header and mode buttons', async () => {
    const { default: AssignmentTrackerCard } = await import(
      '../tabs/analytics/AssignmentTracker'
    );
    render(<AssignmentTrackerCard {...BASE_PROPS} />);

    // Title text
    expect(screen.getByText('Assignment Tracker')).toBeTruthy();

    // Toggle buttons
    expect(screen.getByText('Missing')).toBeTruthy();
    expect(screen.getByText('Submitted')).toBeTruthy();

    // Refresh button
    expect(screen.getByText('Refresh')).toBeTruthy();
  });

  it('renders the empty-periods placeholder when periods is empty', async () => {
    const { default: AssignmentTrackerCard } = await import(
      '../tabs/analytics/AssignmentTracker'
    );
    render(<AssignmentTrackerCard {...BASE_PROPS} />);

    expect(
      screen.getByText('Upload period rosters in Settings to track missing assignments'),
    ).toBeTruthy();
  });

  it('renders TrackerFilters controls (Period / Student / Assignment selects)', async () => {
    const { default: AssignmentTrackerCard } = await import(
      '../tabs/analytics/AssignmentTracker'
    );
    render(<AssignmentTrackerCard {...BASE_PROPS} />);

    expect(screen.getByText('Period')).toBeTruthy();
    expect(screen.getByText('Student')).toBeTruthy();
    expect(screen.getByText('Assignment')).toBeTruthy();
  });

  it('renders PeriodMissingReport summary stats when periods are provided', async () => {
    const { default: AssignmentTrackerCard } = await import(
      '../tabs/analytics/AssignmentTracker'
    );
    const props = {
      ...BASE_PROPS,
      periods: [{ period_name: 'Period 1', filename: 'p1' }],
      sortedPeriods: [{ period_name: 'Period 1', filename: 'p1', students: [] }],
      periodStudentMap: { 'Period 1': [] },
      savedAssignments: ['HW 1'],
      savedAssignmentData: {},
    };
    render(<AssignmentTrackerCard {...props} />);

    // Summary stats labels from PeriodMissingReport.
    // "Missing" also appears on the toggle button, so use getAllByText.
    expect(screen.getAllByText('Missing').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Uploaded')).toBeTruthy();
    expect(screen.getByText('Students')).toBeTruthy();
    expect(screen.getByText('Assignments')).toBeTruthy();
  });
});

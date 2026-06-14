import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Mount smoke test for StaticSections and its extracted child AlertsGrid.
// Added with the CQ wave-3 split (#cq8-04) that extracted AlertsGrid from
// StaticSections. Asserts that key text from both panels renders without
// crashing, confirming props thread correctly through the child boundary.

vi.mock('../tabs/analytics/AssignmentTracker', () => ({
  default: () => <div>Assignment Tracker</div>,
}));

describe('StaticSections mounts without crashing', () => {
  const baseAnalytics = {
    attention_needed: [{ name: 'Alice', average: 55, trend: 'declining' }],
    top_performers: [{ name: 'Bob', average: 97 }],
    cost_summary: null,
  };

  it('renders Needs Attention and Top Performers panels via AlertsGrid', async () => {
    const StaticSections = (await import('../tabs/analytics/StaticSections')).default;
    render(
      <StaticSections
        filteredAnalytics={baseAnalytics}
        periodStudentMap={{}}
        sortedPeriods={[]}
        savedAssignments={[]}
        savedAssignmentData={{}}
        config={{}}
        status={{ results: [] }}
        addToast={vi.fn()}
        periods={[]}
        onStudentClick={vi.fn()}
      />,
    );

    expect(screen.getByText('Needs Attention')).toBeTruthy();
    expect(screen.getByText('Top Performers')).toBeTruthy();
    // Attention student rendered and clickable
    expect(screen.getByText('Alice')).toBeTruthy();
    expect(screen.getByText('55%')).toBeTruthy();
    expect(screen.getByText('declining')).toBeTruthy();
    // Top performer rendered
    expect(screen.getByText('Bob')).toBeTruthy();
    expect(screen.getByText('97%')).toBeTruthy();
    // AssignmentTrackerCard stub rendered
    expect(screen.getByText('Assignment Tracker')).toBeTruthy();
  });

  it('shows "All students are doing well!" when attention_needed is empty', async () => {
    const StaticSections = (await import('../tabs/analytics/StaticSections')).default;
    render(
      <StaticSections
        filteredAnalytics={{ ...baseAnalytics, attention_needed: [] }}
        periodStudentMap={{}}
        sortedPeriods={[]}
        savedAssignments={[]}
        savedAssignmentData={{}}
        config={{}}
        status={{ results: [] }}
        addToast={vi.fn()}
        periods={[]}
        onStudentClick={vi.fn()}
      />,
    );
    expect(screen.getByText('All students are doing well!')).toBeTruthy();
  });
});

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Render-time smoke test for GradeChartsSection + AssignmentAveragesChart child.
// Added with CQ wave-2 split (cq8-04): ensures the extracted AssignmentAveragesChart
// child receives props correctly and key text renders without crashing.
// Uses Vitest native matchers only (toBeTruthy/toBe) — jest-dom is not configured.

describe('GradeChartsSection mounts without crashing (render-time smoke)', () => {
  const filteredAnalytics = {
    class_stats: {
      total_assignments: 3,
      total_students: 2,
      class_average: 82,
      highest: 95,
      lowest: 70,
      grade_distribution: { A: 1, B: 1, C: 1, D: 0, F: 0 },
    },
    all_grades: [
      { student_name: 'Alice', assignment: 'HW 1', score: 90 },
      { student_name: 'Bob', assignment: 'HW 1', score: 74 },
    ],
    assignment_stats: [
      { name: 'HW 1', average: 82 },
    ],
  };

  beforeEach(() => {
    // jsdom has no IntersectionObserver (used by DeferredMount). Must be a
    // real class — the component calls `new IntersectionObserver(...)`.
    global.IntersectionObserver = class {
      observe() {}
      disconnect() {}
      unobserve() {}
    };
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders stats cards and grade distribution heading', async () => {
    vi.useRealTimers();
    const GradeChartsSection = (await import('../tabs/analytics/GradeChartsSection')).default;
    render(
      <GradeChartsSection
        filteredAnalytics={filteredAnalytics}
        periodStudentMap={{}}
      />,
    );

    // Stats cards
    expect(screen.getByText('Total Graded')).toBeTruthy();
    expect(screen.getByText('Students')).toBeTruthy();
    expect(screen.getByText('Class Average')).toBeTruthy();
    expect(screen.getByText('Highest Score')).toBeTruthy();

    // Grade distribution header (from GradeChartsSection itself)
    expect(screen.getByText('Grade Distribution')).toBeTruthy();

    // Assignment Averages heading (rendered by the extracted AssignmentAveragesChart child)
    expect(screen.getByText('Assignment Averages')).toBeTruthy();
  });
});

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Render-time smoke test for AnalyticsTab. Added with the CQ wave-1 split of
// AnalyticsTab.jsx into tabs/analytics/* (mirrors App.mount.test.jsx, which was
// added with the slice-15 App.jsx decomposition for the same reason): before
// this test NOTHING rendered AnalyticsTab — build + unit tests pass even if a
// split leaves an unimported component or mis-threaded prop that white-screens
// the tab at runtime. This mounts the real component tree (hook, filters
// header, charts sections, student panel, tracker, table) end to end.
vi.mock('../services/api', () => ({
  getAnalytics: vi.fn().mockResolvedValue({
    class_stats: {
      total_assignments: 2,
      total_students: 1,
      class_average: 85,
      highest: 90,
      lowest: 80,
      grade_distribution: { A: 1, B: 1, C: 0, D: 0, F: 0 },
    },
    student_progress: [
      {
        name: 'Test Student',
        average: 85,
        trend: 'steady',
        grades: [
          { assignment: 'HW 1', score: 80, date: '2026-05-01' },
          { assignment: 'HW 2', score: 90, date: '2026-05-08' },
        ],
      },
    ],
    all_grades: [
      { student_name: 'Test Student', assignment: 'HW 1', score: 80 },
      { student_name: 'Test Student', assignment: 'HW 2', score: 90 },
    ],
    attention_needed: [],
    top_performers: [{ name: 'Test Student', average: 85 }],
    assignment_stats: [{ name: 'HW 1', average: 80 }],
    category_stats: [],
    available_periods: [],
  }),
  getPeriodStudents: vi.fn().mockResolvedValue({ students: [] }),
  exportDistrictReport: vi.fn().mockResolvedValue({}),
}));

describe('AnalyticsTab mounts without crashing (render-time smoke)', () => {
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

  it('renders the full analytics tree after data loads', { timeout: 20000 }, async () => {
    vi.useRealTimers();
    const AnalyticsTab = (await import('../tabs/AnalyticsTab')).default;
    render(
      <AnalyticsTab
        config={{}}
        status={{ results: [] }}
        periods={[]}
        sortedPeriods={[]}
        savedAssignments={[]}
        savedAssignmentData={{}}
        addToast={vi.fn()}
        assessmentResults={[]}
        teacherClasses={[]}
      />,
    );

    // Header renders once the analytics fetch resolves (AnalyticsFiltersHeader).
    expect(await screen.findByText('Class Analytics')).toBeTruthy();
    // chartsReady flips after a double requestAnimationFrame; these cover each
    // extracted section: GradeChartsSection, StudentPanel (ScatterSection),
    // StaticSections (Top Performers + AssignmentTrackerCard), StudentTable.
    expect(await screen.findByText('Grade Distribution')).toBeTruthy();
    expect(await screen.findByText('Student Proficiency vs Growth')).toBeTruthy();
    expect(await screen.findByText('Top Performers')).toBeTruthy();
    expect(await screen.findByText('Assignment Tracker')).toBeTruthy();
    expect(await screen.findByText('All Students Overview')).toBeTruthy();
  });
});

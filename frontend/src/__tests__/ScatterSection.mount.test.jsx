import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Render-time smoke test for ScatterSection + ScatterProficiencyChart child.
// Added with the CQ wave-3/4 split (cq8-04): ScatterSection's recharts chart
// body was extracted into ScatterProficiencyChart. This pins the wrapper's
// render (heading + description) so a dropped prop / bad import surfaces here
// instead of in the nightly e2e. DeferredMount gates the chart behind an
// IntersectionObserver that never fires in jsdom, so only the card chrome
// renders — exactly mirroring the sibling analytics mount tests.
// Uses Vitest native matchers only (toBeTruthy) — jest-dom is not configured.

describe('ScatterSection mounts without crashing (render-time smoke)', () => {
  const filteredAnalytics = {
    student_progress: [
      {
        name: 'Alice',
        average: 88,
        trend: 'up',
        grades: [{ score: 80 }, { score: 90 }, { score: 95 }],
      },
      {
        name: 'Bob',
        average: 62,
        trend: 'down',
        grades: [{ score: 70 }, { score: 55 }],
      },
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

  it('renders the section heading and description', async () => {
    const ScatterSection = (await import('../tabs/analytics/ScatterSection')).default;
    render(
      <ScatterSection
        filteredAnalytics={filteredAnalytics}
        onStudentClick={() => {}}
      />,
    );
    expect(screen.getByText('Student Proficiency vs Growth')).toBeTruthy();
    expect(screen.getByText(/Click any dot to view/)).toBeTruthy();
  });

  it('renders with empty analytics without crashing', async () => {
    const ScatterSection = (await import('../tabs/analytics/ScatterSection')).default;
    render(
      <ScatterSection
        filteredAnalytics={{}}
        onStudentClick={() => {}}
      />,
    );
    expect(screen.getByText('Student Proficiency vs Growth')).toBeTruthy();
  });
});

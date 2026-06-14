import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

// Render-equivalence net for ApiUsageSummary (extracted from SettingsBilling,
// CQ wave cq8-05). Covers both render branches: the no-data "Load Cost Summary"
// button and the populated breakdown table + "Refresh" button. The two buttons
// call loadCosts with distinct resetOnError args (true for Load, false for
// Refresh) to preserve the original SettingsBilling behavior where Load reset to
// a zeroed fallback on error and Refresh ignored errors.
// Uses Vitest native matchers only (toBeTruthy) — jest-dom is not configured.

vi.mock('../services/api', () => ({
  getAnalytics: vi.fn().mockResolvedValue({ cost_summary: { total_cost: 1.2345, total_graded: 10, avg_cost_per_student: 0.12 } }),
  getPlannerCosts: vi.fn().mockResolvedValue({ total: { total_cost: 0.5, api_calls: 4 } }),
  getAssistantCosts: vi.fn().mockResolvedValue({ total: { total_cost: 0.25, api_calls: 2 } }),
}));

describe('ApiUsageSummary (render-equivalence)', () => {
  it('renders the Load Cost Summary button when no data', async () => {
    const ApiUsageSummary = (await import('../components/ApiUsageSummary')).default;
    render(<ApiUsageSummary costSummary={null} setCostSummary={() => {}} />);
    expect(screen.getByText('Load Cost Summary')).toBeTruthy();
  });

  it('renders the breakdown table + Refresh button when data is present', async () => {
    const ApiUsageSummary = (await import('../components/ApiUsageSummary')).default;
    const costSummary = {
      grading: { total_cost: 1.2345, total_graded: 10, avg_cost_per_student: 0.12 },
      assistant: { total_cost: 0.25, api_calls: 2 },
      planner: { total_cost: 0.5, api_calls: 4 },
    };
    render(<ApiUsageSummary costSummary={costSummary} setCostSummary={() => {}} />);
    expect(screen.getByText('Grading')).toBeTruthy();
    expect(screen.getByText('Assistant')).toBeTruthy();
    expect(screen.getByText('Planner')).toBeTruthy();
    expect(screen.getByText('Total')).toBeTruthy();
    expect(screen.getByText('Refresh')).toBeTruthy();
  });
});

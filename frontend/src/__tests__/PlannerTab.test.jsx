import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PlannerTab from '../tabs/PlannerTab';

// Mock the api module — Planner calls many api.* methods inline. Build out
// as test set grows. Per plan #190, PR 1 is presentational extraction only;
// the focused behavior tests get added in PRs 2-7 alongside the state moves.
vi.mock('../services/api', () => ({
  loadAssignment: vi.fn().mockResolvedValue({ assignment: {} }),
  generateLessonPlan: vi.fn().mockResolvedValue({ lessonPlan: 'Test' }),
  getStandards: vi.fn().mockResolvedValue({ standards: [] }),
  listAssignments: vi.fn().mockResolvedValue({ assignments: [], assignmentData: {} }),
}));

const makeProps = (overrides = {}) => ({
  // App-shell state (read-only)
  status: { results: [], log: [], is_running: false, error: null },
  config: { ai_model: 'gpt-4o', subject: 'Math', grade_level: '8' },
  user: null,
  activeTab: 'planner',
  // App-shell mutators
  setStatus: vi.fn(),
  setConfig: vi.fn(),
  addToast: vi.fn(),
  // Build out as PR 1 build feedback reveals additional prop requirements.
  // Per plan: the prop count is intentionally large (~91 Planner-only states
  // + setters + ~30 App handlers + constants). Each state default is
  // permissive (empty array, empty object, false, null).
  ...overrides,
});

describe('PlannerTab', () => {
  it('smoke: renders without crashing with minimal props', () => {
    // PR 1 smoke test. Per plan, focused behavior tests added in subsequent
    // PRs alongside state moves (Grade-tab Round 2 MAJOR pattern).
    render(<PlannerTab {...makeProps()} />);
  });
});

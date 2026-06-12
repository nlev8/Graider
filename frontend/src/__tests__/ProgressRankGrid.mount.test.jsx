import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ProgressRankGrid from '../tabs/ProgressRankGrid';

// Content-asserting mount test for ProgressRankGrid. Added with the CQ
// wave-8 split of ProgressRankGrid.jsx into tabs/progress-rank-grid/*
// (mirrors RemediationDrawer.mount.test.jsx from wave 6, for the same
// reason): `npm run build` only proves imports resolve, not that every
// relocated identifier is still in scope at render time. These tests mount
// every extracted branch (rank table with red-tier header CTAs, cell
// popover with contributing submissions, the conditionally-mounted
// RemediationDrawer path) with real data so a missed prop in the split
// surfaces as a ReferenceError/TypeError here, not in production. Written
// and run GREEN against the pre-split file first.

vi.mock('../services/api', () => ({
  getClassProgressRank: vi.fn(),
  // Used by the (real) RemediationDrawer this component conditionally mounts.
  postRemediate: vi.fn(),
  publishToClass: vi.fn(),
  publishToClassBatch: vi.fn(),
}));

import * as api from '../services/api';

const rankResponse = {
  class_name: 'Period 5',
  standards: ['MATH.7.EE.1', 'MATH.7.EE.2'],
  students: [
    {
      student_id: 's1', student_name: 'Ada Lovelace',
      mastery: {
        'MATH.7.EE.1': {
          percentage: 92, points_earned: 23, points_possible: 25, question_count: 5,
          contributing_submissions: [
            { title: 'Quiz 1', attempt_number: 1, points_earned: 23, points_possible: 25 },
          ],
        },
        'MATH.7.EE.2': {
          percentage: 78, points_earned: 7, points_possible: 9, question_count: 3,
          contributing_submissions: [],
        },
      },
    },
    {
      student_id: 's2', student_name: 'Alan Turing',
      mastery: {
        'MATH.7.EE.1': {
          percentage: 55, points_earned: 11, points_possible: 20, question_count: 4,
          contributing_submissions: [
            { title: 'Quiz 1', attempt_number: 2, points_earned: 11, points_possible: 20 },
          ],
        },
        // No MATH.7.EE.2 data — renders the em-dash placeholder cell.
      },
    },
  ],
};

describe('ProgressRankGrid mounts with content from every extracted section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getClassProgressRank.mockResolvedValue(rankResponse);
  });

  it('renders the loading spinner first, then header + controls', async () => {
    render(<ProgressRankGrid classId="class-1" />);
    expect(screen.getByText('Loading progress rank...')).toBeTruthy();
    expect(await screen.findByText(/Progress Rank/)).toBeTruthy();
    expect(screen.getByText(/Period 5/)).toBeTruthy();
    expect(screen.getByText(/2 students/)).toBeTruthy();
    expect(screen.getByText('Latest')).toBeTruthy();
    expect(screen.getByText('Best')).toBeTruthy();
    expect(screen.getByText('Average')).toBeTruthy();
    expect(screen.getByText('All Students')).toBeTruthy();
    expect(screen.getByText('Struggling Only')).toBeTruthy();
  });

  it('renders the grid: standard headers, student rows, mastery cells', async () => {
    render(<ProgressRankGrid classId="class-1" />);
    await screen.findByText('Ada Lovelace');
    expect(screen.getByText('MATH.7.EE.1')).toBeTruthy();
    expect(screen.getByText('MATH.7.EE.2')).toBeTruthy();
    expect(screen.getByText('Alan Turing')).toBeTruthy();
    expect(screen.getByText('92%')).toBeTruthy();
    expect(screen.getByText('78%')).toBeTruthy();
    expect(screen.getByText('55%')).toBeTruthy();
    // Red-tier column header CTA (one student <70 on MATH.7.EE.1)
    expect(screen.getByText('Remediate (1)')).toBeTruthy();
  });

  it('filters to struggling students only', async () => {
    render(<ProgressRankGrid classId="class-1" />);
    await screen.findByText('Ada Lovelace');
    fireEvent.click(screen.getByText('Struggling Only'));
    expect(screen.queryByText('Ada Lovelace')).toBeNull();
    expect(screen.getByText('Alan Turing')).toBeTruthy();
  });

  it('clicking a mastery cell opens the popover with contributing submissions', async () => {
    render(<ProgressRankGrid classId="class-1" />);
    await screen.findByText('Alan Turing');
    fireEvent.click(screen.getByText('55%'));
    expect(screen.getByText('Contributing submissions')).toBeTruthy();
    expect(screen.getByText(/11\/20 pts across 4 questions/)).toBeTruthy();
    expect(screen.getByText('Quiz 1')).toBeTruthy();
    expect(screen.getByText(/Attempt 2/)).toBeTruthy();
    // <85% mastery shows the remediation CTA
    expect(screen.getByText('Generate remediation')).toBeTruthy();
  });

  it('popover "Generate remediation" closes the popover and mounts the drawer', async () => {
    render(<ProgressRankGrid classId="class-1" />);
    await screen.findByText('Alan Turing');
    // Drawer is NOT mounted until triggered (conditional-unmount parent).
    expect(screen.queryByText('Remediation: MATH.7.EE.1')).toBeNull();
    fireEvent.click(screen.getByText('55%'));
    fireEvent.click(screen.getByText('Generate remediation'));
    expect(screen.queryByText('Contributing submissions')).toBeNull();
    expect(screen.getByText('Remediation: MATH.7.EE.1')).toBeTruthy();
    expect(screen.getByText('Configure remediation')).toBeTruthy();
  });

  it('red-tier header CTA mounts the drawer in red_tier_in_class mode', async () => {
    render(<ProgressRankGrid classId="class-1" />);
    await screen.findByText('Ada Lovelace');
    fireEvent.click(screen.getByText('Remediate (1)'));
    expect(screen.getByText('Remediation: MATH.7.EE.1')).toBeTruthy();
  });

  it('renders the empty state when no standards are assessed', async () => {
    api.getClassProgressRank.mockResolvedValue({
      class_name: 'Period 5', standards: [], students: [],
    });
    render(<ProgressRankGrid classId="class-1" />);
    expect(await screen.findByText(/No standards-tagged assessments yet/)).toBeTruthy();
  });

  it('renders the error state on API error', async () => {
    api.getClassProgressRank.mockResolvedValue({ error: 'boom' });
    render(<ProgressRankGrid classId="class-1" />);
    expect(await screen.findByText('boom')).toBeTruthy();
  });
});

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import RemediationEffectiveness from '../tabs/RemediationEffectiveness';

// Content-asserting mount test for RemediationEffectiveness. Added with the
// CQ wave-8 split of RemediationEffectiveness.jsx into
// tabs/remediation-effectiveness/* (mirrors RemediationDrawer.mount.test.jsx
// from wave 6, for the same reason): `npm run build` only proves imports
// resolve, not that every relocated identifier is still in scope at render
// time. These tests mount every extracted branch (per-remediation card with
// the before/after table, DOK expander rows, recall confirm modal, the
// always-mounted RemediationDrawer toggle path) with real data so a missed
// prop in the split surfaces as a ReferenceError/TypeError here, not in
// production. Written and run GREEN against the pre-split file first.

vi.mock('../services/api', () => ({
  getClassRemediationEffectiveness: vi.fn(),
  recallRemediation: vi.fn(),
  // Used by the (real) RemediationDrawer this component keeps mounted.
  postRemediate: vi.fn(),
  publishToClass: vi.fn(),
  publishToClassBatch: vi.fn(),
}));

import * as api from '../services/api';

const effectivenessResponse = {
  class_name: 'Period 3',
  remediations: [
    {
      remediation_id: 'rem-1',
      title: 'Fractions Reteach',
      standard_code: 'MATH.7.EE.1',
      created_at: '2026-05-01T12:00:00Z',
      target_count: 2,
      is_active: true,
      rows: [
        {
          student_id: 's1', student_name: 'Ada Lovelace',
          before: 40, after: 55, delta: 15,
          completed: true, attempt_count: 2,
          before_by_dok: { 2: 35, 3: 50 },
          after_by_dok: { 2: 60, 3: 50 },
          delta_by_dok: { 2: 25, 3: 0 },
        },
        {
          student_id: 's2', student_name: 'Alan Turing',
          before: null, after: 70, delta: null,
          completed: false, attempt_count: 0,
        },
      ],
    },
    {
      remediation_id: 'rem-2',
      title: 'Recalled One',
      standard_code: 'MATH.7.EE.2',
      created_at: '2026-05-02T12:00:00Z',
      target_count: 1,
      is_active: false,
      rows: [],
    },
  ],
};

const makeProps = (overrides = {}) => ({
  classId: 'class-1',
  addToast: vi.fn(),
  ...overrides,
});

describe('RemediationEffectiveness mounts with content from every extracted section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getClassRemediationEffectiveness.mockResolvedValue(effectivenessResponse);
    api.recallRemediation.mockResolvedValue({ recalled: true });
  });

  it('renders the loading spinner first, then header + card content', async () => {
    render(<RemediationEffectiveness {...makeProps()} />);
    expect(screen.getByText('Loading effectiveness...')).toBeTruthy();
    expect(await screen.findByText(/Remediation Effectiveness/)).toBeTruthy();
    expect(screen.getByText(/Period 3/)).toBeTruthy();
    // Per-remediation card header
    expect(screen.getByText('Fractions Reteach')).toBeTruthy();
    expect(screen.getByText('MATH.7.EE.1')).toBeTruthy();
    expect(screen.getByText(/2 students/)).toBeTruthy();
  });

  it('renders the before/after table rows with delta badges and CTAs', async () => {
    render(<RemediationEffectiveness {...makeProps()} />);
    await screen.findByText('Ada Lovelace');
    expect(screen.getByText('40%')).toBeTruthy();
    expect(screen.getByText('55%')).toBeTruthy();
    expect(screen.getByText('+15%')).toBeTruthy();
    expect(screen.getByText('Yes')).toBeTruthy();
    // Row without a baseline shows the No-baseline badge
    expect(screen.getByText('Alan Turing')).toBeTruthy();
    expect(screen.getByText('No baseline')).toBeTruthy();
    expect(screen.getAllByText('Remediate again').length).toBe(2);
    // Inactive remediation shows the Recalled badge instead of the button
    expect(screen.getByText('Recalled')).toBeTruthy();
    expect(screen.getAllByText('Recall').length).toBe(1);
  });

  it('expands the per-row DOK breakdown', async () => {
    render(<RemediationEffectiveness {...makeProps()} />);
    await screen.findByText('Ada Lovelace');
    // Only the row with DOK data gets the expander
    const dokToggles = screen.getAllByText(/DOK$/);
    expect(dokToggles.length).toBe(1);
    fireEvent.click(dokToggles[0]);
    expect(screen.getByText('DOK 2')).toBeTruthy();
    expect(screen.getByText('DOK 3')).toBeTruthy();
    expect(screen.getByText('35%')).toBeTruthy();
    expect(screen.getByText('60%')).toBeTruthy();
    expect(screen.getByText('+25')).toBeTruthy();
  });

  it('"Remediate again" opens the always-mounted drawer (toggle path)', async () => {
    render(<RemediationEffectiveness {...makeProps()} />);
    await screen.findByText('Ada Lovelace');
    // Drawer is mounted but closed: its header is absent.
    expect(screen.queryByText('Remediation: MATH.7.EE.1')).toBeNull();
    fireEvent.click(screen.getAllByText('Remediate again')[0]);
    expect(screen.getByText('Remediation: MATH.7.EE.1')).toBeTruthy();
    expect(screen.getByText('Configure remediation')).toBeTruthy();
  });

  it('Recall opens the confirm modal with submitted-count copy, Cancel closes it', async () => {
    render(<RemediationEffectiveness {...makeProps()} />);
    await screen.findByText('Ada Lovelace');
    fireEvent.click(screen.getByText('Recall'));
    expect(screen.getByText('Recall this remediation?')).toBeTruthy();
    expect(screen.getByText(/1 student already submitted/)).toBeTruthy();
    fireEvent.click(screen.getByText('Cancel'));
    expect(screen.queryByText('Recall this remediation?')).toBeNull();
  });

  it('confirming Recall calls the API, toasts, and reloads', async () => {
    const props = makeProps();
    render(<RemediationEffectiveness {...props} />);
    await screen.findByText('Ada Lovelace');
    fireEvent.click(screen.getByText('Recall'));
    const confirmBtns = screen.getAllByText('Recall');
    fireEvent.click(confirmBtns[confirmBtns.length - 1]);
    await waitFor(() => {
      expect(api.recallRemediation).toHaveBeenCalledWith('class-1', 'rem-1');
    });
    await waitFor(() => {
      expect(props.addToast).toHaveBeenCalled();
    });
    // Reload: fetch ran again (initial + post-recall)
    expect(api.getClassRemediationEffectiveness).toHaveBeenCalledTimes(2);
  });

  it('renders the empty state when no remediations exist', async () => {
    api.getClassRemediationEffectiveness.mockResolvedValue({
      class_name: 'Period 3', remediations: [],
    });
    render(<RemediationEffectiveness {...makeProps()} />);
    expect(await screen.findByText('No remediations published yet.')).toBeTruthy();
  });

  it('renders the error state on API error', async () => {
    api.getClassRemediationEffectiveness.mockResolvedValue({ error: 'boom' });
    render(<RemediationEffectiveness {...makeProps()} />);
    expect(await screen.findByText('boom')).toBeTruthy();
  });
});

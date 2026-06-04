import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../services/api', () => ({
  sendEmails: vi.fn(),
  sendOutlookEmails: vi.fn(),
  updateApproval: vi.fn(),
  updateApprovalsBulk: vi.fn(),
}));

import * as api from '../../services/api';
import { useResultsCurveAndEmail } from '../useResultsCurveAndEmail';

// Characterization net for the App.jsx -> useResultsCurveAndEmail extraction (slice 12).
// Pins the curve math + the email/approval handlers. getLetterGrade is internal to the
// factory (used by applyCurve); getDefaultEmailBody is passed in.
function setup(over = {}) {
  const fns = {};
  for (const s of [
    'addToast', 'setEditedResults', 'setEditedEmails', 'setStatus', 'setCurveModal',
    'setEmailPreview', 'setEmailStatus', 'setEmailApprovals', 'setOutlookSendPolling',
    'setOutlookSendStatus',
  ]) fns[s] = vi.fn();
  const props = {
    status: { results: [{ score: 80, period: '1' }] },
    resultsPeriodFilter: '',
    editedResults: [],
    editedEmails: {},
    curveModal: { curveType: 'add', curveValue: 5 },
    emailPreview: { show: true },
    config: { teacher_email: 't@s.org', teacher_name: 'T', email_signature: 'sig' },
    getDefaultEmailBody: vi.fn(() => 'default body'),
    ...fns,
    ...over,
  };
  const { result } = renderHook(() => useResultsCurveAndEmail(props));
  return { result, props };
}

describe('useResultsCurveAndEmail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.sendEmails.mockResolvedValue({ sent: 1, failed: 0 });
    api.sendOutlookEmails.mockResolvedValue({ total: 1 });
    api.updateApproval.mockResolvedValue({});
    api.updateApprovalsBulk.mockResolvedValue({});
  });

  it('applyCurve "add": raises the score, recomputes the grade, marks edited, toasts', () => {
    const { result, props } = setup();
    result.current.applyCurve();
    const saved = props.setEditedResults.mock.calls[0][0];
    expect(saved[0]).toMatchObject({ score: 85, letter_grade: 'B', edited: true });
    expect(props.setStatus).toHaveBeenCalled();
    expect(props.setCurveModal).toHaveBeenCalledWith({ curveType: 'add', curveValue: 5, show: false });
    expect(props.addToast).toHaveBeenCalledWith(expect.stringContaining('Applied +5 points curve to 1 result'), 'success');
  });

  it('applyCurve: warns and does nothing when the curve value is 0', () => {
    const { result, props } = setup({ curveModal: { curveType: 'add', curveValue: 0 } });
    result.current.applyCurve();
    expect(props.addToast).toHaveBeenCalledWith('Please enter a curve value', 'warning');
    expect(props.setEditedResults).not.toHaveBeenCalled();
  });

  it('applyCurve: warns when no results match the filter', () => {
    const { result, props } = setup({ status: { results: [] } });
    result.current.applyCurve();
    expect(props.addToast).toHaveBeenCalledWith('No results to curve', 'warning');
  });

  it('sendEmails: posts the results with teacher config and updates status', async () => {
    const { result, props } = setup();
    await result.current.sendEmails();
    expect(props.setEmailPreview).toHaveBeenCalledWith({ show: false });
    expect(api.sendEmails).toHaveBeenCalledWith([{ score: 80, period: '1' }], 't@s.org', 'T', 'sig');
    expect(props.setEmailStatus).toHaveBeenLastCalledWith(expect.objectContaining({ sending: false, sent: 1 }));
  });

  it('sendSingleEmail: errors when there is no email address', async () => {
    const { result, props } = setup();
    await result.current.sendSingleEmail({ student_name: 'Y' }, 0); // no student_email, no edited email
    expect(props.addToast).toHaveBeenCalledWith('No email address for Y', 'error');
    expect(api.sendOutlookEmails).not.toHaveBeenCalled();
  });

  it('sendSingleEmail: sends via Outlook and starts polling', async () => {
    const { result, props } = setup();
    await result.current.sendSingleEmail({ student_name: 'X', student_email: 'x@s.org', assignment: 'HW' }, 0);
    expect(api.sendOutlookEmails).toHaveBeenCalled();
    expect(props.setOutlookSendPolling).toHaveBeenCalledWith(true);
    expect(props.addToast).toHaveBeenCalledWith('Sending via Outlook to X', 'info');
  });

  it('updateApprovalStatus: sets the approval, updates status, persists', async () => {
    const { result, props } = setup({ status: { results: [{ filename: 'a.docx', score: 80 }] } });
    await result.current.updateApprovalStatus(0, 'approved');
    expect(props.setEmailApprovals).toHaveBeenCalled();
    expect(props.setStatus).toHaveBeenCalled();
    expect(api.updateApproval).toHaveBeenCalledWith('a.docx', 'approved');
  });

  it('updateApprovalsBulk: sets all and persists the filename map', async () => {
    const { result, props } = setup({ status: { results: [{ filename: 'a.docx' }, { filename: 'b.docx' }] } });
    await result.current.updateApprovalsBulk({ 0: 'approved', 1: 'rejected' });
    expect(props.setEmailApprovals).toHaveBeenCalledWith({ 0: 'approved', 1: 'rejected' });
    expect(api.updateApprovalsBulk).toHaveBeenCalledWith({ 'a.docx': 'approved', 'b.docx': 'rejected' });
  });
});

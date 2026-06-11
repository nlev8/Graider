import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ReviewModal from '../components/ReviewModal';
vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));
const base = () => ({
  reviewModal: { show: true, index: 0 },
  status: { results: [{ name: 'Student', filename: 'a.pdf', score: 90, feedback: '', sections: [], questions: [] }] },
  editedResults: {}, editedEmails: {}, emailApprovals: {}, sentEmails: {},
  autoApproveEmails: false, showAIReasoning: false, config: {},
  reviewModalTab: 'detected', reviewModalRightTab: 'edit',
});
const makeProps = (o = {}) => new Proxy({ ...base(), ...o }, { get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); }, has() { return true; } });
describe('ReviewModal', () => {
  it('smoke: renders without crashing', () => {
    const { container } = render(<ReviewModal {...makeProps()} />);
    expect(container).toBeTruthy();
  });
});

// Added alongside the CQ wave-4 split of ReviewModal.jsx into
// components/review-modal/*. The split relocated ~950 lines of JSX into 8
// stateless child components; the build only proves imports resolve, not that
// every relocated identifier is still in scope at render time. These tests
// mount every branch of the composed tree (detected-responses tab incl.
// unanswered + empty states, raw tab incl. text / handwritten-image / no-path
// variants, grade & feedback tab incl. late penalty + section breakdown +
// re-translate + AI reasoning, email preview tab incl. approval buttons in
// all states + auto-approve + signature variants, the missing-result guard)
// so a missed prop surfaces as a ReferenceError here instead of in production.
describe('ReviewModal branch mounts (review-modal/* split)', () => {
  const result = (over = {}) => ({
    student_name: 'Jane Doe', assignment: 'Essay 1', filename: 'jane.pdf',
    score: 85, letter_grade: 'B', feedback: 'Good work overall',
    student_responses: ['Photosynthesis converts light'],
    unanswered_questions: ['Question 3'],
    ...over,
  });
  const props = (r = result(), over = {}) =>
    makeProps({ ...base(), status: { results: [r] }, ...over });

  it('mounts detected-responses tab with responses + unanswered list', () => {
    render(<ReviewModal {...props()} />);
    expect(screen.getByText(/Detected Responses/)).toBeTruthy();
    expect(screen.getByText('Photosynthesis converts light')).toBeTruthy();
    expect(screen.getByText(/Unanswered \(1\)/)).toBeTruthy();
    expect(screen.getByText('Question 3')).toBeTruthy();
    // header renders student name; footer renders Done
    expect(screen.getByRole('heading').textContent).toContain('Jane Doe');
    expect(screen.getByText('Done')).toBeTruthy();
  });

  it('mounts detected tab empty state', () => {
    render(<ReviewModal {...props(result({ student_responses: [], unanswered_questions: [] }))} />);
    expect(screen.getByText('No student responses detected')).toBeTruthy();
  });

  it('mounts raw tab with plain text content', () => {
    render(<ReviewModal {...props(result({ full_content: 'RAW TEXT CONTENT' }), { reviewModalTab: 'raw' })} />);
    expect(screen.getByText('RAW TEXT CONTENT')).toBeTruthy();
  });

  it('mounts raw tab handwritten-image branch (with and without path)', () => {
    const { unmount } = render(
      <ReviewModal {...props(result({ is_handwritten: true, filepath: '/tmp/scan.png' }), { reviewModalTab: 'raw' })} />,
    );
    expect(screen.getByText('Handwritten Assignment')).toBeTruthy();
    expect(screen.getByAltText('jane.pdf').getAttribute('src')).toContain('serve-file');
    unmount();
    render(<ReviewModal {...props(result({ is_handwritten: true }), { reviewModalTab: 'raw' })} />);
    expect(screen.getByText(/extracted by AI vision/)).toBeTruthy();
  });

  it('mounts grade & feedback tab with late penalty, section breakdown, re-translate, AI reasoning', () => {
    const r = result({
      feedback: 'English part\n---\nParte traducida',
      late_penalty: { days_late: 2, penalty_applied: 10 },
      original_score: 95,
      section_scores: { Vocabulary: { earned: 3, possible: 5 } },
    });
    render(<ReviewModal {...props(r)} />);
    expect(screen.getByDisplayValue('85')).toBeTruthy(); // score input
    expect(screen.getByText('B')).toBeTruthy(); // letter grade chip
    expect(screen.getByText('Late Submission')).toBeTruthy();
    expect(screen.getByText('Remove Penalty')).toBeTruthy();
    expect(screen.getByText('Section Breakdown')).toBeTruthy();
    expect(screen.getByText('3/5 pts')).toBeTruthy();
    expect(screen.getByText('Re-translate')).toBeTruthy();
    expect(screen.getByText('AI Reasoning')).toBeTruthy();
  });

  it('mounts email preview tab with approval buttons in default state', () => {
    render(<ReviewModal {...props(result({ student_email: 'jane@school.edu' }), { reviewModalRightTab: 'email' })} />);
    expect(screen.getByDisplayValue('jane@school.edu')).toBeTruthy();
    expect(screen.getByText(/Subject:/)).toBeTruthy();
    expect(screen.getByText('Approve Email')).toBeTruthy();
    expect(screen.getByText('Reject')).toBeTruthy();
    expect(screen.getByText('Mark as Sent')).toBeTruthy();
    expect(screen.getByText('Your Teacher')).toBeTruthy(); // default signature
  });

  it('mounts email tab approved/sent button states and (not found) email warning', () => {
    render(<ReviewModal {...props(result(), {
      reviewModalRightTab: 'email',
      emailApprovals: { 0: 'approved' },
      sentEmails: { 0: true },
    })} />);
    expect(screen.getByText('Approved')).toBeTruthy();
    expect(screen.getByText('Sent')).toBeTruthy();
    expect(screen.getByText('(not found)')).toBeTruthy();
  });

  it('email tab hides approval buttons when autoApproveEmails, custom signature shown', () => {
    render(<ReviewModal {...props(result(), {
      reviewModalRightTab: 'email',
      autoApproveEmails: true,
      config: { email_signature: 'Cheers, Ms. Frizzle' },
    })} />);
    expect(screen.queryByText('Approve Email')).toBeNull();
    expect(screen.getByText(/Cheers, Ms. Frizzle/)).toBeTruthy();
  });

  it('editedResults takes precedence over status.results', () => {
    render(<ReviewModal {...props(result(), {
      editedResults: { 0: result({ student_name: 'Edited Name', student_responses: ['EDITED RESP'] }) },
    })} />);
    expect(screen.getByRole('heading').textContent).toContain('Edited Name');
    expect(screen.getByText('EDITED RESP')).toBeTruthy();
  });

  it('renders header + footer but no body when the indexed result is missing', () => {
    render(<ReviewModal {...makeProps({ ...base(), reviewModal: { show: true, index: 5 } })} />);
    expect(screen.getByText('Done')).toBeTruthy();
    expect(screen.queryByText(/Detected Responses/)).toBeNull();
  });
});

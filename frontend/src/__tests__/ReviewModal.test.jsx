import React from 'react';
import { render } from '@testing-library/react';
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

import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import EmailPreviewModal from '../components/EmailPreviewModal';
vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));
const base = () => ({ emailPreview: { show: true, emails: [] } });
const makeProps = (o = {}) => new Proxy({ ...base(), ...o }, { get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); }, has() { return true; } });
describe('EmailPreviewModal', () => {
  it('smoke: renders without crashing', () => {
    const { container } = render(<EmailPreviewModal {...makeProps()} />);
    expect(container).toBeTruthy();
  });
});

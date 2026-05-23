import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SettingsGeneral from '../components/SettingsGeneral';

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

const base = () => ({
  config: { subject: 'Math', grade_level: '8', state: 'FL', email_signature: '', extraction_mode: 'structured' },
  apiKeys: {},
  adminStatus: null,
  adminClaimResult: null,
  adminClaimCode: '',
  rubric: { categories: [], gradingStyle: 'standard' },
  availableStates: [],
  periods: [],
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('SettingsGeneral', () => {
  it('smoke: renders without crashing', () => {
    const { container } = render(<SettingsGeneral {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });
});

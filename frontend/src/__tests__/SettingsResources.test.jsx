import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SettingsResources from '../components/SettingsResources';

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

const base = () => ({
  supportDocs: [],
  newDocType: 'curriculum',
  newDocDescription: '',
  uploadingDoc: false,
  supportDocInputRef: { current: null },
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('SettingsResources', () => {
  it('smoke: renders without crashing', () => {
    const { container } = render(<SettingsResources {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });
});

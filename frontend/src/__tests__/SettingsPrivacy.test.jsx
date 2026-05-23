import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SettingsPrivacy from '../components/SettingsPrivacy';

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

const base = () => ({
  config: { subject: 'Math', grade_level: '8' },
  periods: [],
  studentHistoryList: [],
  studentHistoryLoading: false,
  selectedStudentHistory: null,
  exportStudentSearch: { active: false, query: '', results: [], allStudents: [] },
  importStudentData: { active: false, preview: null, file: null, importing: false, selectedPeriod: '' },
  importFileRef: { current: null },
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('SettingsPrivacy', () => {
  it('smoke: renders without crashing', () => {
    const { container } = render(<SettingsPrivacy {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });
});

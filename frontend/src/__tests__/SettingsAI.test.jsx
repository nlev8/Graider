import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SettingsAI from '../components/SettingsAI';

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

const base = () => ({
  config: { ai_model: 'gpt-4o', assistant_model: 'gpt-4o', assistant_voice: 'alloy', ensemble_enabled: false, ensemble_models: [], extraction_mode: 'structured' },
  apiKeys: {},
  globalAINotes: '',
  showApiKeys: { openai: false, anthropic: false, gemini: false },
  savingApiKeys: false,
  MODEL_COST_PER_ASSIGNMENT: {},
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('SettingsAI', () => {
  it('smoke: renders without crashing', () => {
    const { container } = render(<SettingsAI {...makeProps()} />);
    expect(container.firstChild).toBeTruthy();
  });
});

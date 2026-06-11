import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import SettingsAI from '../components/SettingsAI';

// Content-asserting mount test for SettingsAI. Added with the CQ wave-5 split
// of SettingsAI.jsx into settings-ai/* (mirrors SettingsPrivacy.mount.test.jsx
// from wave 4, for the same reason): before this test, the only renderer was
// the no-crash smoke in SettingsAI.test.jsx, which passes even if a split
// leaves an unimported section component or a mis-threaded prop that blanks
// part of the panel at runtime. This test asserts real content from every
// extracted section actually mounts.

vi.mock('../services/api', () => new Proxy({}, { get: () => vi.fn().mockResolvedValue({}) }));

const base = () => ({
  config: {
    ai_model: 'gpt-4o-mini',
    assistant_model: 'haiku',
    assistant_voice: 'nova',
    ensemble_enabled: false,
    ensemble_models: [],
    extraction_mode: 'structured',
  },
  apiKeys: { openai: '', anthropic: '', gemini: '' },
  globalAINotes: '',
  showApiKeys: { openai: false, anthropic: false, gemini: false },
  savingApiKeys: false,
  MODEL_COST_PER_ASSIGNMENT: {},
});
const makeProps = (over = {}) => new Proxy({ ...base(), ...over }, {
  get(t, p) { if (p in t) return t[p]; if (typeof p === 'symbol') return undefined; return vi.fn(); },
  has() { return true; },
});

describe('SettingsAI mounts with content from every extracted section', () => {
  it('renders model selection, extraction mode, ensemble, instructions, API keys, and assistant sections', () => {
    render(<SettingsAI {...makeProps()} />);

    // ModelSelectionSection — header, model option, unconfigured-key notice
    expect(screen.getByText('AI Model')).toBeTruthy();
    expect(screen.getByText('GPT-4o Mini (Fast & Cheap)')).toBeTruthy();
    expect(screen.getByText('Add OpenAI API key below to use GPT')).toBeTruthy();
    // ExtractionModeSection — header + both radio labels
    expect(screen.getByText('Response Extraction Mode')).toBeTruthy();
    expect(screen.getByText('Structured')).toBeTruthy();
    expect(screen.getByText('AI-Powered')).toBeTruthy();
    // EnsembleGradingSection — toggle label; model list hidden while disabled
    expect(screen.getByText('Ensemble Grading')).toBeTruthy();
    expect(screen.queryByText('GPT-4o Mini')).toBeNull();
    // GlobalInstructionsSection — header
    expect(screen.getByText('Global AI Instructions')).toBeTruthy();
    // ApiKeysSection — header + all three key fields + save button
    expect(screen.getByText('API Keys')).toBeTruthy();
    expect(screen.getByText('OpenAI API Key')).toBeTruthy();
    expect(screen.getByText('Anthropic (Claude) API Key')).toBeTruthy();
    expect(screen.getByText('Google AI (Gemini) API Key')).toBeTruthy();
    expect(screen.getByText('Save API Keys')).toBeTruthy();
    // AssistantModelSection — header
    expect(screen.getByText('AI Assistant Model')).toBeTruthy();
    // AssistantVoiceSection — header + a voice option
    expect(screen.getByText('Assistant Voice')).toBeTruthy();
    expect(screen.getByText('Nova — Bright, engaging (default)')).toBeTruthy();
  });

  it('renders the ensemble model list, cost estimate, and configured-key states', () => {
    render(
      <SettingsAI
        {...makeProps({
          config: {
            ai_model: 'claude-sonnet',
            assistant_model: 'haiku',
            assistant_voice: 'nova',
            ensemble_enabled: true,
            ensemble_models: ['gpt-4o-mini', 'claude-haiku'],
            extraction_mode: 'ai',
          },
          apiKeys: {
            openai: '', anthropic: '', gemini: '',
            openaiConfigured: true, anthropicConfigured: true, geminiConfigured: false,
            openaiIsOwn: true,
          },
          MODEL_COST_PER_ASSIGNMENT: { 'gpt-4o-mini': 0.001, 'claude-haiku': 0.002 },
        })}
      />
    );

    // ModelSelectionSection — own keys unlock extra models; Claude model shows
    // the Anthropic-connected notice
    expect(screen.getByText('Claude Sonnet (Balanced)')).toBeTruthy();
    expect(screen.getByText('Anthropic API connected')).toBeTruthy();
    // EnsembleGradingSection enabled branch — model rows, per-model cost,
    // missing-key warning for Gemini, and the 2-model cost estimate
    expect(screen.getByText('GPT-4o Mini')).toBeTruthy();
    expect(screen.getByText('Claude Haiku')).toBeTruthy();
    expect(screen.getAllByText('No API key').length).toBe(2);
    expect(screen.getByText(/2 models selected - estimated ~\$0\.0030\/assignment/)).toBeTruthy();
    // ApiKeysSection configured branch — "Connected" badges for OpenAI + Anthropic
    expect(screen.getAllByText('Connected').length).toBe(2);
  });
});

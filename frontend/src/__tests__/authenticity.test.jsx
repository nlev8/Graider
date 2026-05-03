/**
 * Tests for the authenticity helpers (utils/authenticity.js).
 */
import { describe, it, expect } from 'vitest';
import {
  getAuthenticityStatus,
  getAIFlagColor,
  getPlagFlagColor,
} from '../utils/authenticity';

describe('getAuthenticityStatus', () => {
  it('returns clean overallStatus when both flags are none (new format)', () => {
    const r = {
      ai_detection: { flag: 'none', confidence: 0, reason: '' },
      plagiarism_detection: { flag: 'none', reason: '' },
    };
    const out = getAuthenticityStatus(r);
    expect(out.overallStatus).toBe('clean');
    expect(out.isNewFormat).toBe(true);
  });

  it('returns flagged when ai is likely', () => {
    const r = { ai_detection: { flag: 'likely', confidence: 90 } };
    expect(getAuthenticityStatus(r).overallStatus).toBe('flagged');
  });

  it('returns flagged when plag is likely', () => {
    const r = { plagiarism_detection: { flag: 'likely' } };
    expect(getAuthenticityStatus(r).overallStatus).toBe('flagged');
  });

  it('returns review when ai is possible but plag is none', () => {
    const r = { ai_detection: { flag: 'possible' } };
    expect(getAuthenticityStatus(r).overallStatus).toBe('review');
  });

  it('uses old-format fallback when no detection objects present', () => {
    const r = { authenticity_flag: 'flagged', authenticity_reason: 'copied' };
    const out = getAuthenticityStatus(r);
    expect(out.isNewFormat).toBe(false);
    expect(out.overallStatus).toBe('flagged');
    expect(out.ai.flag).toBe('likely');
    expect(out.ai.confidence).toBe(80);
    expect(out.ai.reason).toBe('copied');
    expect(out.plag.flag).toBe('none');
  });

  it('old-format review maps to ai.flag=possible / confidence=50', () => {
    const r = { authenticity_flag: 'review', authenticity_reason: 'unsure' };
    const out = getAuthenticityStatus(r);
    expect(out.ai.flag).toBe('possible');
    expect(out.ai.confidence).toBe(50);
  });

  it('old-format clean leaves ai.reason empty', () => {
    const r = { authenticity_flag: 'clean', authenticity_reason: 'irrelevant' };
    const out = getAuthenticityStatus(r);
    expect(out.ai.flag).toBe('none');
    expect(out.ai.reason).toBe('');
  });
});

describe('getAIFlagColor', () => {
  it.each([
    ['likely', '#f87171'],
    ['possible', '#fbbf24'],
    ['unlikely', '#60a5fa'],
    ['none', '#4ade80'],
    ['anything-else', '#4ade80'],
  ])('flag=%s → text color %s', (flag, color) => {
    expect(getAIFlagColor(flag).text).toBe(color);
  });
});

describe('getPlagFlagColor', () => {
  it.each([
    ['likely', '#f87171'],
    ['possible', '#fbbf24'],
    ['none', '#4ade80'],
    ['anything-else', '#4ade80'],
    // Note: 'unlikely' is NOT in plag's switch, falls to default
    ['unlikely', '#4ade80'],
  ])('flag=%s → text color %s', (flag, color) => {
    expect(getPlagFlagColor(flag).text).toBe(color);
  });
});

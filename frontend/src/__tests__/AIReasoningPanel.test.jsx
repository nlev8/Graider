/**
 * Tests for AIReasoningPanel.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import AIReasoningPanel from '../components/AIReasoningPanel';

describe('AIReasoningPanel', () => {
  it('renders nothing when open is false', () => {
    const { container } = render(
      <AIReasoningPanel open={false} aiInput="..." aiResponse="..." />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders both labels and the input/response when open', () => {
    render(
      <AIReasoningPanel
        open={true}
        aiInput="prompt text here"
        aiResponse='{"score": 90}'
      />
    );
    expect(screen.getByText('Prompt Input (Sent to AI)')).toBeDefined();
    expect(screen.getByText('Raw API Output (JSON)')).toBeDefined();
    expect(screen.getByText('prompt text here')).toBeDefined();
    expect(screen.getByText('{"score": 90}')).toBeDefined();
  });

  it('falls back to "Not available" when aiInput is empty', () => {
    render(<AIReasoningPanel open={true} aiInput="" aiResponse="something" />);
    expect(screen.getByText('Not available')).toBeDefined();
  });

  it('falls back to "Not available" when aiResponse is undefined', () => {
    render(<AIReasoningPanel open={true} aiInput="something" aiResponse={undefined} />);
    expect(screen.getByText('Not available')).toBeDefined();
  });
});

import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import InteractiveProbabilityTree from '../components/InteractiveProbabilityTree.jsx';

// Render-equivalence net for the ProbabilityTreeCanvas extraction (CQ8 wave 2).
// A passing render proves every prop the child reads is supplied by the parent.
describe('InteractiveProbabilityTree (mount)', () => {
  it('renders the SVG tree canvas at the expected dimensions', () => {
    const { container } = render(<InteractiveProbabilityTree />);
    const svg = container.querySelector('svg');
    expect(svg).toBeTruthy();
    expect(svg.getAttribute('width')).toBe('560');
    expect(svg.getAttribute('height')).toBe('360');
  });

  it('renders the outcomes table for the default coin-flip tree', () => {
    const { getByText } = render(<InteractiveProbabilityTree />);
    expect(getByText('Outcomes:')).toBeTruthy();
  });

  it('disables the final-answer input in readOnly mode when an answer key is present', () => {
    const { container } = render(
      <InteractiveProbabilityTree answers={{ total_1: '' }} readOnly={true} />,
    );
    const input = container.querySelector('input[placeholder="e.g. 1/4"]');
    expect(input).toBeTruthy();
    expect(input.disabled).toBe(true);
  });
});

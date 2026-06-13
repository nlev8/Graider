import { render, screen } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import InteractiveFunctionGraph from '../components/InteractiveFunctionGraph.jsx';

// Canvas is not available in jsdom; stub getContext so the useEffect doesn't throw.
beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    fillText: vi.fn(),
    setLineDash: vi.fn(),
    getPropertyValue: vi.fn(() => ''),
  }));
});

describe('InteractiveFunctionGraph mount', () => {
  test('renders input controls in interactive mode', () => {
    render(
      <InteractiveFunctionGraph
        xRange={[-5, 5]}
        yRange={[-5, 5]}
        expressions={['x^2']}
      />
    );
    // Input panel should be present with the expression value
    const input = screen.getByRole('textbox');
    expect(input).toBeTruthy();
    expect(input.value).toBe('x^2');
  });

  test('renders Add function button when below maxExpressions', () => {
    render(
      <InteractiveFunctionGraph
        xRange={[-10, 10]}
        yRange={[-10, 10]}
        expressions={['']}
        maxExpressions={3}
      />
    );
    expect(screen.getByText('+ Add function')).toBeTruthy();
  });

  test('hides input controls in readOnly mode', () => {
    render(
      <InteractiveFunctionGraph
        xRange={[-5, 5]}
        yRange={[-5, 5]}
        expressions={['x']}
        readOnly={true}
      />
    );
    // No text input in readOnly mode
    expect(screen.queryByRole('textbox')).toBeNull();
  });

  test('renders a canvas element', () => {
    const { container } = render(
      <InteractiveFunctionGraph
        xRange={[-10, 10]}
        yRange={[-10, 10]}
      />
    );
    expect(container.querySelector('canvas')).toBeTruthy();
  });
});

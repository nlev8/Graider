import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import InteractiveNumberLine from '../components/InteractiveNumberLine';

// Render-equivalence net for InteractiveNumberLine — added with the CQ wave-2
// split that extracted NumberLineSvg into components/interactive-number-line/.
// Asserts the component mounts without error and renders its key UI regions
// before and after the split (render-equivalence proof).

describe('InteractiveNumberLine', () => {
  it('renders hint text when not readOnly', () => {
    render(
      <InteractiveNumberLine
        minVal={-5}
        maxVal={5}
        points={[]}
        onChange={() => {}}
      />
    );
    expect(
      screen.getByText(/click on the number line to plot points/i)
    ).toBeTruthy();
  });

  it('does not render hint when readOnly', () => {
    render(
      <InteractiveNumberLine
        minVal={-5}
        maxVal={5}
        points={[]}
        readOnly
      />
    );
    expect(
      screen.queryByText(/click on the number line to plot points/i)
    ).toBeNull();
  });

  it('renders plotted points list when points are present', () => {
    render(
      <InteractiveNumberLine
        minVal={-5}
        maxVal={5}
        points={[1, -3]}
        onChange={() => {}}
      />
    );
    expect(screen.getByText(/plotted points/i)).toBeTruthy();
    expect(screen.getByText(/1\.00/)).toBeTruthy();
  });

  it('renders an SVG canvas', () => {
    const { container } = render(
      <InteractiveNumberLine
        minVal={0}
        maxVal={10}
        points={[]}
        onChange={() => {}}
      />
    );
    expect(container.querySelector('svg')).toBeTruthy();
  });
});

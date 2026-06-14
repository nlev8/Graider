import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import InteractiveTransformations from '../components/InteractiveTransformations.jsx';

// Render-equivalence net added with the CQ wave-2 split of InteractiveTransformations.jsx
// (TransformationCanvas extracted to interactive-transformations/TransformationCanvas.jsx).
// Ensures the SVG canvas and key UI elements remain connected after the pure-prop extraction.

describe('InteractiveTransformations', () => {
  it('renders the transformation label for translation (default)', () => {
    render(
      <InteractiveTransformations
        transformationType="translation"
        transformParams={{ dx: 3, dy: 2 }}
      />
    );
    expect(screen.getByText(/Translation/)).toBeTruthy();
  });

  it('renders an SVG canvas element', () => {
    const { container } = render(<InteractiveTransformations />);
    expect(container.querySelector('svg')).toBeTruthy();
  });

  it('renders the plot hint text in plot mode', () => {
    render(
      <InteractiveTransformations mode="plot" readOnly={false} />
    );
    expect(screen.getByText(/Click grid points/)).toBeTruthy();
  });

  it('renders identify mode input when mode is identify', () => {
    render(
      <InteractiveTransformations
        mode="identify"
        transformationType="reflection"
        transformParams={{ axis: 'y-axis' }}
      />
    );
    expect(screen.getByPlaceholderText(/e\.g\. reflection/)).toBeTruthy();
    expect(screen.getByText(/Identify the transformation/)).toBeTruthy();
  });

  it('renders user vertices list when vertices are provided', () => {
    render(
      <InteractiveTransformations
        userVertices={[[2, 3], [5, 3]]}
        mode="plot"
      />
    );
    expect(screen.getByText(/Your vertices/)).toBeTruthy();
    expect(screen.getByText(/A'\(2, 3\)/)).toBeTruthy();
  });

  it('renders the reflection label for reflection type', () => {
    render(
      <InteractiveTransformations
        transformationType="reflection"
        transformParams={{ axis: 'x-axis' }}
      />
    );
    expect(screen.getByText(/Reflection over x-axis/)).toBeTruthy();
  });

  it('renders dilation label with correct scale factor', () => {
    render(
      <InteractiveTransformations
        transformationType="dilation"
        transformParams={{ scale: 3, centerX: 0, centerY: 0 }}
      />
    );
    expect(screen.getByText(/Dilation scale factor 3/)).toBeTruthy();
  });

  it('renders rotation label with correct degrees', () => {
    render(
      <InteractiveTransformations
        transformationType="rotation"
        transformParams={{ degrees: 180, centerX: 0, centerY: 0 }}
      />
    );
    expect(screen.getByText(/Rotation 180/)).toBeTruthy();
  });
});

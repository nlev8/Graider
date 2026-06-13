import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import InteractiveCoordinatePlane from '../components/InteractiveCoordinatePlane';

// Render-equivalence net added with the CQ wave-2 split of
// InteractiveCoordinatePlane.jsx into interactive-coordinate-plane/CoordinatePlaneCanvas.jsx.
// Mounts the real component tree and asserts the SVG canvas plus the points
// legend are present — catching any mis-threaded prop or unimported child that
// would cause a white-screen at runtime.

describe('InteractiveCoordinatePlane mount', () => {
  it('renders the SVG canvas', () => {
    const { container } = render(
      <InteractiveCoordinatePlane xRange={[-6, 6]} yRange={[-6, 6]} points={[]} />
    );
    const svg = container.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg.getAttribute('width')).toBe('400');
    expect(svg.getAttribute('height')).toBe('400');
  });

  it('renders axis labels x and y inside the SVG', () => {
    const { container } = render(
      <InteractiveCoordinatePlane xRange={[-6, 6]} yRange={[-6, 6]} points={[]} />
    );
    const texts = Array.from(container.querySelectorAll('text'));
    const textContents = texts.map(t => t.textContent);
    expect(textContents).toContain('x');
    expect(textContents).toContain('y');
  });

  it('renders quadrant labels when showQuadrants=true', () => {
    const { container } = render(
      <InteractiveCoordinatePlane xRange={[-6, 6]} yRange={[-6, 6]} points={[]} showQuadrants={true} />
    );
    const texts = Array.from(container.querySelectorAll('text')).map(t => t.textContent);
    expect(texts).toContain('I');
    expect(texts).toContain('II');
    expect(texts).toContain('III');
    expect(texts).toContain('IV');
  });

  it('renders plotted points legend when points provided', () => {
    const { container } = render(
      <InteractiveCoordinatePlane
        xRange={[-6, 6]}
        yRange={[-6, 6]}
        points={[[3, 4], [-2, 1]]}
        labels={['P', 'Q']}
      />
    );
    // Points legend text visible
    expect(container.textContent).toContain('Plotted points');
    expect(container.textContent).toContain('P(3, 4)');
    expect(container.textContent).toContain('Q(-2, 1)');
  });

  it('renders hint text when not readOnly', () => {
    const { container } = render(
      <InteractiveCoordinatePlane xRange={[-6, 6]} yRange={[-6, 6]} points={[]} readOnly={false} />
    );
    expect(container.textContent).toContain('Click to plot points');
  });

  it('hides hint text in readOnly mode', () => {
    const { container } = render(
      <InteractiveCoordinatePlane xRange={[-6, 6]} yRange={[-6, 6]} points={[]} readOnly={true} />
    );
    expect(container.textContent).not.toContain('Click to plot points');
  });
});

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import InteractiveProtractor from '../components/InteractiveProtractor.jsx';

/**
 * Render-equivalence net for InteractiveProtractor.
 * Added with the CQ 7→8 wave-2 split of InteractiveProtractor.jsx into
 * interactive-protractor/ProtractorCanvas.jsx (Protocol-FE mount test).
 * Asserts the key UI regions (SVG canvas, classification panel, answer input)
 * render correctly both before and after the child-component extraction.
 */
describe('InteractiveProtractor', () => {
  it('renders SVG canvas in measure mode', () => {
    render(
      <InteractiveProtractor
        givenAngle={45}
        mode="measure"
        answer=""
        userAngle={0}
      />
    );
    // SVG should be present (the canvas is a child SVG element)
    const svgEls = document.querySelectorAll('svg');
    expect(svgEls.length).toBeGreaterThan(0);
    // Answer label present
    expect(screen.getByText('What is the angle?')).toBeTruthy();
    // Answer input present
    const input = screen.getByPlaceholderText('e.g. 45');
    expect(input).toBeTruthy();
  });

  it('shows classification panel when showClassification=true and angle>0', () => {
    render(
      <InteractiveProtractor
        givenAngle={45}
        mode="measure"
        answer=""
        userAngle={0}
        showClassification={true}
      />
    );
    // Classification panel shows the angle type
    expect(screen.getByText('acute')).toBeTruthy();
  });

  it('shows right-angle classification for 90 degrees', () => {
    render(
      <InteractiveProtractor
        givenAngle={90}
        mode="measure"
        answer=""
        userAngle={0}
        showClassification={true}
      />
    );
    expect(screen.getByText('right')).toBeTruthy();
  });

  it('renders classify mode label', () => {
    render(
      <InteractiveProtractor
        givenAngle={120}
        mode="classify"
        answer=""
        userAngle={0}
      />
    );
    expect(screen.getByText('Classify this angle:')).toBeTruthy();
    const input = screen.getByPlaceholderText('e.g. acute');
    expect(input).toBeTruthy();
  });

  it('renders construct mode with hint and target angle', () => {
    render(
      <InteractiveProtractor
        givenAngle={null}
        targetAngle={60}
        mode="construct"
        answer=""
        userAngle={30}
        readOnly={false}
      />
    );
    // Hint text includes the target angle
    expect(screen.getByText(/Target: 60/)).toBeTruthy();
  });

  it('disables input when readOnly', () => {
    render(
      <InteractiveProtractor
        givenAngle={45}
        mode="measure"
        answer="45"
        userAngle={0}
        readOnly={true}
      />
    );
    const input = screen.getByDisplayValue('45');
    expect(input.disabled).toBe(true);
  });

  it('shows correct answer hint when correctAnswer matches', () => {
    render(
      <InteractiveProtractor
        givenAngle={45}
        mode="measure"
        answer="acute"
        userAngle={0}
        correctAnswer="acute"
      />
    );
    // Checkmark character ✓ (U+2713)
    expect(screen.getByText('✓')).toBeTruthy();
  });
});
